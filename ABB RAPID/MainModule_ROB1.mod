MODULE MainModule_ROB1

    ! ====================================================
    ! PHASE 1: INTERRUPT-DRIVEN FEEDBACK (ExitCycle Approach)
    ! ====================================================
    ! Uses ExitCycle from TRAP to restart main() on interrupt.
    ! RAISE cannot escape a TRAP in RAPID (confirmed 2026-02-10).
    ! ====================================================

    ! --- INTERRUPT CONFIGURATION ---
    VAR intnum ir_stop_trigger_R1;

    ! TODO: Configure this DI signal name to match your actual hardware
    CONST string DI_INTERRUPT_SIGNAL := "diInterruptSignal";

    ! Shared flags to indicate interrupt occurred (read by commModule and other task)
    PERS bool wasInterrupted_R1 := FALSE;
    PERS bool wasInterrupted_R2 := FALSE;

    ! PHASE 2: Streaming variables (shared with commModule)
    PERS string operationMode := "d";
    PERS jointtarget streamJointTarget_R1 := [[0,0,0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    PERS bool newStreamTarget_R1 := FALSE;

    PROC main()
        TPErase;

        ! Always re-setup interrupt (ExitCycle clears connections)
        Setup_Interrupt_R1;

        IF wasInterrupted_R1 THEN
            ! ExitCycle restart — skip init, go straight to idle loop
            TPWrite "R1: Restarted after interrupt.";
            KeepLooping;
        ENDIF

        ! Normal first-run initialization
        TPWrite "R1: Main module started.";
        assignWaypoints;

        ConfJ \Off;
        state_HOME;
        ConfJ \On;

        KeepLooping;
    ENDPROC

    ! ====================================================
    ! INTERRUPT SETUP (runs on every main() entry)
    ! ====================================================
    PROC Setup_Interrupt_R1()
        Safe_IDelete_R1;
        CONNECT ir_stop_trigger_R1 WITH trap_handle_stop_R1;
        ISignalDI DI_INTERRUPT_SIGNAL, 1, ir_stop_trigger_R1;
        TPWrite "R1: Interrupt configured on " + DI_INTERRUPT_SIGNAL;

    ERROR
        IF ERRNO = ERR_INOMAX THEN
            TPWrite "R1: WARNING - Max interrupts reached.";
        ELSEIF ERRNO = ERR_SIGSUPSEARCH THEN
            TPWrite "R1: ERROR - DI signal '" + DI_INTERRUPT_SIGNAL + "' not found!";
        ELSE
            TPWrite "R1: Interrupt setup error:" \Num:=ERRNO;
        ENDIF
    ENDPROC

    ! IDelete isolated so its error doesn't skip CONNECT/ISignalDI
    PROC Safe_IDelete_R1()
        IDelete ir_stop_trigger_R1;
    ERROR
        TRYNEXT;
    ENDPROC

    PROC KeepLooping()
        WHILE TRUE DO
            IF newTargetFlag_R1 = TRUE THEN
                newTargetFlag_R1 := FALSE;
                IF smIndx = "d" THEN
                    Run_Motion_Manager_R1;
                ELSEIF smIndx = "I" THEN
                    TPWrite "R1, ACK to client";
                ELSEIF smIndx = "T" THEN
                    TPWrite "R1, comm closed by client";
                ELSE
                    TPWrite "Invalid robot index." + smIndx;
                ENDIF

                executionNotCompleted_R1 := FALSE;
                TPWrite "R1, execution completed, waiting for next command.";
            ENDIF

            ! PHASE 2: Joint streaming check (independent of newTargetFlag)
            IF newStreamTarget_R1 = TRUE THEN
                newStreamTarget_R1 := FALSE;
                Run_Joint_Stream_R1;
                executionNotCompleted_R1 := FALSE;
            ENDIF

            WaitTime 0.25;
        ENDWHILE
    ENDPROC

    ! ====================================================
    ! MOTION MANAGER
    ! ====================================================
    PROC Run_Motion_Manager_R1()
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

        ! Interrupt-aware sync: if the other robot was interrupted and
        ! ExitCycled, it will never reach this sync point. Skip to avoid deadlock.
        IF NOT wasInterrupted_R1 AND NOT wasInterrupted_R2 THEN
            WaitSyncTask syncEND, all_tasks;
        ELSE
            TPWrite "R1: Sync skipped - interrupt detected.";
        ENDIF

        TPWrite "R1: Motion completed successfully.";
    ENDPROC

    PROC executeState (num pathChoice, num stateChoice, absPointStruct tempPointStruct)
        VAR string stateChoiceString;
        VAR tooldata toolTemp;
        VAR wobjdata tempWobj;

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
        ENDTEST
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
    PROC Run_Joint_Stream_R1()
        TPWrite "R1: Executing joint stream target";
        MoveAbsJ streamJointTarget_R1, v1000, z5, tool0;
        TPWrite "R1: Joint stream motion completed.";
    ENDPROC

    ! ====================================================
    ! TRAP HANDLER - uses ExitCycle (RAISE cannot escape TRAP)
    ! ====================================================
    TRAP trap_handle_stop_R1
        TPWrite "R1: !!! TRAP TRIGGERED - DI Interrupt !!!";

        StopMove;
        ClearPath;
        StartMove;

        ! Set PERS flags before ExitCycle (commModule reads these)
        wasInterrupted_R1 := TRUE;
        executionNotCompleted_R1 := FALSE;

        ExitCycle;
    ENDTRAP

ENDMODULE
