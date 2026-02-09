MODULE MainModule_ROB1

    ! ====================================================
    ! PHASE 1: INTERRUPT-DRIVEN FEEDBACK IMPLEMENTATION
    ! ====================================================
    ! This module implements the "Global Eject" strategy for
    ! handling digital input interrupts during motion execution.
    ! ====================================================

    ! --- INTERRUPT CONFIGURATION ---
    CONST errnum ERR_INTERRUPT := 99;
    VAR intnum ir_stop_trigger_R1;

    ! TODO: Configure this DI signal name to match your actual hardware
    ! Example: "diEmergencyStop", "diSafetyStop", "diInterruptBtn"
    CONST string DI_INTERRUPT_SIGNAL := "diInterruptSignal";

    ! Shared flag to indicate interrupt occurred
    PERS bool wasInterrupted_R1 := FALSE;

    ! PHASE 2: Streaming variables (shared with commModule)
    PERS string operationMode := "d";
    PERS jointtarget streamJointTarget_R1 := [[0,0,0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    PERS bool newStreamTarget_R1 := FALSE;

    PROC main()
        TPErase;
        TPWrite "R1: Main module started.";

        ! Setup interrupt handler
        Setup_Interrupt_R1;

        assignWaypoints;

        ConfJ \Off;
        state_HOME;
        ConfJ \On;

        KeepLooping;
    ENDPROC

    ! ====================================================
    ! INTERRUPT SETUP PROCEDURE
    ! ====================================================
    PROC Setup_Interrupt_R1()
        ! Delete any existing interrupt connection (safety measure)
        IDelete ir_stop_trigger_R1;

        ! Connect interrupt to TRAP handler
        CONNECT ir_stop_trigger_R1 WITH trap_handle_stop_R1;

        ! Link interrupt to DI signal (trigger on rising edge = 1)
        ISignalDI DI_INTERRUPT_SIGNAL, 1, ir_stop_trigger_R1;

        TPWrite "R1: Interrupt handler configured on " + DI_INTERRUPT_SIGNAL;

    ERROR
        IF ERRNO = ERR_INOMAX THEN
            TPWrite "R1: WARNING - Max interrupts already defined. Check system configuration.";
        ELSEIF ERRNO = ERR_SIGSUPSEARCH THEN
            TPWrite "R1: ERROR - DI signal '" + DI_INTERRUPT_SIGNAL + "' not found!";
            TPWrite "R1: Please configure the signal in I/O System Configuration.";
        ELSE
            TPWrite "R1: Error setting up interrupt: "\Num:=ERRNO;
        ENDIF
    ENDPROC

    PROC KeepLooping()
        WHILE TRUE DO
            IF newTargetFlag_R1 = TRUE THEN
                newTargetFlag_R1 := FALSE;
                IF smIndx = "d" THEN
                    ! Execute motion with interrupt protection
                    Run_Motion_Manager_R1;

                ELSEIF smIndx = "I" THEN
                    TPWrite "R1, ACK to client";
                ELSEIF smIndx = "T" THEN
                    TPWrite "R1, comm closed by client";
                ELSE
                    TPWrite "Invalid robot index." + smIndx;
                ENDIF

                ! Only reset if not interrupted (manager handles it otherwise)
                IF NOT wasInterrupted_R1 THEN
                    executionNotCompleted_R1 := FALSE;
                    TPWrite "R1, execution completed, waiting for next command.";
                ENDIF
            ENDIF

            ! PHASE 2: Joint streaming check (independent of newTargetFlag)
            IF newStreamTarget_R1 = TRUE THEN
                newStreamTarget_R1 := FALSE;
                Run_Joint_Stream_R1;
                IF NOT wasInterrupted_R1 THEN
                    executionNotCompleted_R1 := FALSE;
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
    PROC Run_Motion_Manager_R1()
        ! Reset interrupt flag at start of each motion
        wasInterrupted_R1 := FALSE;

        ! Execute the motion sequence
        TEST pathChoice
        CASE 1:
            TPWrite "R1: Executing path 1";
            executeState pathChoice, stateChoice, absPoints_obj1_R1;
        CASE 2:
            TPWrite "R1: Executing path 2";
            executeState pathChoice, stateChoice, absPoints_obj2_R1;
        DEFAULT:
            TPWrite "R1: Invalid path choice.";
        ENDTEST

        WaitSyncTask syncEND, all_tasks;

        ! --- IF SUCCESSFUL (No interrupt occurred) ---
        ! Normal completion - flag will be reset in KeepLooping
        TPWrite "R1: Motion completed successfully.";

    ERROR
        IF ERRNO = ERR_INTERRUPT THEN
            ! ====================================================
            ! INTERRUPT DETECTED - GLOBAL EJECT TRIGGERED
            ! ====================================================
            TPWrite "R1: *** MOTION INTERRUPTED BY DI SIGNAL ***";

            ! Set the interrupt flag for commModule to detect
            wasInterrupted_R1 := TRUE;

            ! Reset execution flag so commModule knows this robot is done
            ! commModule waits for BOTH R1 and R2 before sending unified ACK
            executionNotCompleted_R1 := FALSE;

            ! Return to KeepLooping to wait for next command
            ! This cancels the rest of the motion sequence
            RETURN;
        ELSE
            ! Handle other errors
            TPWrite "R1: Unexpected error in motion: "\Num:=ERRNO;
            executionNotCompleted_R1 := FALSE;
            RETURN;
        ENDIF
    ENDPROC

    PROC executeState (num pathChoice, num stateChoice, absPointStruct tempPointStruct)
        VAR string stateChoiceString;
        VAR tooldata toolTemp;
        VAR wobjdata tempWobj;

        ! Adjust the TCP based on the modification
        toolTemp := tempPointStruct.defaultTool;
        tempRobTarget_R1 := getAbsPoint(tempPointStruct, stateChoice);
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
        
        absPoints_obj1_R1.defaultWobj := wobj_R1_mold;
        absPoints_obj1_R1.defaultTool := tool_R1_gripper;
        absPoints_obj1_R1.Standby := obj1_standby_R1;

        absPoints_obj2_R1.defaultWobj := wobj_R1_mold;
        absPoints_obj2_R1.defaultTool := tool_R1_gripper;
        absPoints_obj2_R1.Standby := obj2_standby_R1;
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
    ! PHASE 2: JOINT STREAMING MOTION PROCEDURE
    ! ====================================================
    ! Executes a single joint target received from streaming.
    ! Uses MoveAbsJ with zone data for blending.
    ! Protected by the same Global Eject interrupt pattern.
    ! ====================================================
    PROC Run_Joint_Stream_R1()
        wasInterrupted_R1 := FALSE;

        TPWrite "R1: Executing joint stream target";

        ! Use MoveAbsJ with zone data for blending (z5 for smooth streaming)
        MoveAbsJ streamJointTarget_R1, v1000, z5, tool0;

        TPWrite "R1: Joint stream motion completed.";

    ERROR
        IF ERRNO = ERR_INTERRUPT THEN
            TPWrite "R1: *** JOINT STREAM INTERRUPTED BY DI SIGNAL ***";
            wasInterrupted_R1 := TRUE;
            executionNotCompleted_R1 := FALSE;
            RETURN;
        ELSE
            TPWrite "R1: Unexpected error in joint stream: "\Num:=ERRNO;
            executionNotCompleted_R1 := FALSE;
            RETURN;
        ENDIF
    ENDPROC

    ! ====================================================
    ! TRAP HANDLER - INTERRUPT SERVICE ROUTINE
    ! ====================================================
    ! This trap executes immediately when the DI signal triggers.
    ! It performs physical motor stop and raises an error to
    ! trigger the "Global Eject" logic in the ERROR handler.
    ! ====================================================
    TRAP trap_handle_stop_R1
        TPWrite "R1: !!! TRAP TRIGGERED - Emergency Stop Initiated !!!";

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
        ! This raises the custom error that bubbles up to Run_Motion_Manager_R1
        ! The ERROR handler there will set flags and return cleanly
        RAISE ERR_INTERRUPT;
    ENDTRAP

ENDMODULE