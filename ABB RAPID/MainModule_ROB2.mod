MODULE MainModule_ROB2

    ! ====================================================
    ! PHASE 1: INTERRUPT-DRIVEN FEEDBACK IMPLEMENTATION
    ! ====================================================
    ! This module implements the "Global Eject" strategy for
    ! handling digital input interrupts during motion execution.
    ! ====================================================

    ! --- INTERRUPT CONFIGURATION ---
    CONST errnum ERR_INTERRUPT := 99;
    VAR intnum ir_stop_trigger_R2;

    ! TODO: Configure this DI signal name to match your actual hardware
    ! Example: "diEmergencyStop", "diSafetyStop", "diInterruptBtn"
    CONST string DI_INTERRUPT_SIGNAL := "diInterruptSignal";

    ! Shared flag to indicate interrupt occurred
    PERS bool wasInterrupted_R2 := FALSE;

    PROC main()
        TPErase;
        TPWrite "R2: Main module started.";

        ! Setup interrupt handler
        Setup_Interrupt_R2;

        assignWaypoints;

        ConfJ \Off;
        state_HOME;
        ConfJ \On;

        KeepLooping;
    ENDPROC

    ! ====================================================
    ! INTERRUPT SETUP PROCEDURE
    ! ====================================================
    PROC Setup_Interrupt_R2()
        ! Delete any existing interrupt connection (safety measure)
        IDelete ir_stop_trigger_R2;

        ! Connect interrupt to TRAP handler
        CONNECT ir_stop_trigger_R2 WITH trap_handle_stop_R2;

        ! Link interrupt to DI signal (trigger on rising edge = 1)
        ISignalDI DI_INTERRUPT_SIGNAL, 1, ir_stop_trigger_R2;

        TPWrite "R2: Interrupt handler configured on " + DI_INTERRUPT_SIGNAL;

    ERROR
        IF ERRNO = ERR_INOMAX THEN
            TPWrite "R2: WARNING - Max interrupts already defined. Check system configuration.";
        ELSEIF ERRNO = ERR_SIGSUPSEARCH THEN
            TPWrite "R2: ERROR - DI signal '" + DI_INTERRUPT_SIGNAL + "' not found!";
            TPWrite "R2: Please configure the signal in I/O System Configuration.";
        ELSE
            TPWrite "R2: Error setting up interrupt: "\Num:=ERRNO;
        ENDIF
    ENDPROC

    PROC KeepLooping()
        WHILE TRUE DO
            IF newTargetFlag_R2 = TRUE THEN
                newTargetFlag_R2 := FALSE;
                IF smIndx = "d" THEN
                    ! Execute motion with interrupt protection
                    Run_Motion_Manager_R2;

                ELSEIF smIndx = "I" THEN
                    TPWrite "R2, ACK to client";
                ELSEIF smIndx = "T" THEN
                    TPWrite "R2, comm closed by client";
                ELSE
                    TPWrite "Invalid robot index." + smIndx;
                ENDIF

                ! Only reset if not interrupted (manager handles it otherwise)
                IF NOT wasInterrupted_R2 THEN
                    executionNotCompleted_R2 := FALSE;
                    TPWrite "R2, execution completed, waiting for next command.";
                ENDIF
            ENDIF
            WaitTime 0.25; ! wait for a short time before checking the flag again
        ENDWHILE
    ENDPROC

    ! ====================================================
    ! MOTION MANAGER WITH ERROR HANDLING (Global Eject)
    ! ====================================================
    ! This procedure wraps the motion execution and handles
    ! interrupts by catching ERR_INTERRUPT errors.
    ! If interrupted, it sets the flag and returns cleanly.
    ! ====================================================
    PROC Run_Motion_Manager_R2()
        ! Reset interrupt flag at start of each motion
        wasInterrupted_R2 := FALSE;

        ! Execute the motion sequence
        TEST pathChoice
        CASE 1:
            TPWrite "R2: Executing path 1";
            executeState pathChoice, stateChoice, absPoints_obj1_R2;
        CASE 2:
            TPWrite "R2: Executing path 2";
            executeState pathChoice, stateChoice, absPoints_obj2_R2;
        DEFAULT:
            TPWrite "R2: Invalid path choice.";
        ENDTEST

        WaitSyncTask syncEND, all_tasks;

        ! --- IF SUCCESSFUL (No interrupt occurred) ---
        ! Normal completion - flag will be reset in KeepLooping
        TPWrite "R2: Motion completed successfully.";

    ERROR
        IF ERRNO = ERR_INTERRUPT THEN
            ! ====================================================
            ! INTERRUPT DETECTED - GLOBAL EJECT TRIGGERED
            ! ====================================================
            TPWrite "R2: *** MOTION INTERRUPTED BY DI SIGNAL ***";

            ! Set the interrupt flag for commModule to detect
            wasInterrupted_R2 := TRUE;

            ! Reset execution flag so commModule can send ACK_SKIPPED
            executionNotCompleted_R2 := FALSE;

            ! Return to KeepLooping to wait for next command
            ! This cancels the rest of the motion sequence
            RETURN;
        ELSE
            ! Handle other errors
            TPWrite "R2: Unexpected error in motion: "\Num:=ERRNO;
            executionNotCompleted_R2 := FALSE;
            RETURN;
        ENDIF
    ENDPROC

    PROC executeState (num pathChoice, num stateChoice, absPointStruct tempPointStruct)
        VAR string stateChoiceString;
        VAR tooldata toolTemp;
        VAR wobjdata tempWobj;

        ! Adjust the TCP based on the modification
        toolTemp := tempPointStruct.defaultTool;
        tempRobTarget_R2 := getAbsPoint(tempPointStruct, stateChoice);
        tempWobj := tempPointStruct.defaultWobj;

        stateChoiceString := findState(stateChoice);

        TEST stateChoiceString
        CASE "Home":
            TPWrite "Moving to Home position.";
            state_HOME;
        CASE "Standby":
            TPWrite "Moving to Standby position.";
            state_STANDBY;
        DEFAULT:
            TPWrite "Wrong state chosen.";            
    ENDPROC

    PROC assignWaypoints()
        
        absPoints_obj1_R2.defaultWobj := wobj_R2_mold;
        absPoints_obj1_R2.defaultTool := tool_R2_gripper;
        absPoints_obj1_R2.Standby := obj1_standby_R2;

        absPoints_obj2_R2.defaultWobj := wobj_R2_mold;
        absPoints_obj2_R2.defaultTool := tool_R2_gripper;
        absPoints_obj2_R2.Standby := obj2_standby_R2;
    ENDPROC

    FUNC string findState (num stateChoice)
        VAR string stateString;
        TEST stateChoice
        CASE 1:
            stateString := "Home";
        CASE 2:
            stateString := "Standby";
        DEFAULT:
            stateString := "Invalid";
        ENDTEST

        RETURN stateString;
    ENDFUNC

    FUNC robtarget getAbsPoint (absPointStruct pointStruct, num stateChoice)
        VAR robtarget tempTarget;
        TEST stateChoice
        CASE 1:
            tempTarget := pointStruct.Home;
        CASE 2:
            tempTarget := pointStruct.Standby;
        DEFAULT:
            TPWrite "Invalid state choice for getting absolute point.";
        ENDTEST

        RETURN tempTarget;
    ENDFUNC

    ! ====================================================
    ! TRAP HANDLER - INTERRUPT SERVICE ROUTINE
    ! ====================================================
    ! This trap executes immediately when the DI signal triggers.
    ! It performs physical motor stop and raises an error to
    ! trigger the "Global Eject" logic in the ERROR handler.
    ! ====================================================
    TRAP trap_handle_stop_R2
        TPWrite "R2: !!! TRAP TRIGGERED - Emergency Stop Initiated !!!";

        ! 1. STOP THE MOTORS IMMEDIATELY
        ! This halts all motion on this mechanical unit
        StopMove;

        ! 2. CLEAR THE MOTION PATH
        ! Without this, StartMove would try to finish the interrupted move
        ! ClearPath removes all pending motion instructions from the queue
        ClearPath;

        ! 3. RE-ENABLE MOTION SYSTEM
        ! Allows the robot to accept new motion commands later
        ! Without this, the robot would remain in a stopped state
        StartMove;

        ! 4. TRIGGER THE GLOBAL EJECT
        ! This raises the custom error that bubbles up to Run_Motion_Manager_R2
        ! The ERROR handler there will set flags and return cleanly
        RAISE ERR_INTERRUPT;
    ENDTRAP

ENDMODULE