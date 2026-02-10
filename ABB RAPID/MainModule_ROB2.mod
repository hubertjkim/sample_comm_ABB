MODULE MainModule_ROB2

    ! ====================================================
    ! PHASE 1: INTERRUPT-DRIVEN FEEDBACK (ExitCycle Approach)
    ! ====================================================
    ! Uses ExitCycle from TRAP to restart main() on interrupt.
    ! RAISE cannot escape a TRAP in RAPID (confirmed 2026-02-10).
    ! ====================================================

    ! --- INTERRUPT CONFIGURATION ---
    VAR intnum ir_stop_trigger_R2;

    ! TODO: Configure this DI signal name to match your actual hardware
    CONST string DI_INTERRUPT_SIGNAL := "diInterruptSignal";

    ! Shared flags to indicate interrupt occurred (read by commModule and other task)
    PERS bool wasInterrupted_R1 := FALSE;
    PERS bool wasInterrupted_R2 := FALSE;

    ! PHASE 2: Streaming variables (declared for cross-task PERS compatibility)
    PERS string operationMode := "d";

    PROC main()
        TPErase;

        ! Always re-setup interrupt (ExitCycle clears connections)
        Setup_Interrupt_R2;

        IF wasInterrupted_R2 THEN
            ! ExitCycle restart — skip init, go straight to idle loop
            TPWrite "R2: Restarted after interrupt.";
            KeepLooping;
        ENDIF

        ! Normal first-run initialization
        TPWrite "R2: Main module started.";
        assignWaypoints;

        ConfJ \Off;
        state_HOME;
        ConfJ \On;

        KeepLooping;
    ENDPROC

    ! ====================================================
    ! INTERRUPT SETUP (runs on every main() entry)
    ! ====================================================
    PROC Setup_Interrupt_R2()
        Safe_IDelete_R2;
        CONNECT ir_stop_trigger_R2 WITH trap_handle_stop_R2;
        ISignalDI DI_INTERRUPT_SIGNAL, 1, ir_stop_trigger_R2;
        TPWrite "R2: Interrupt configured on " + DI_INTERRUPT_SIGNAL;

    ERROR
        IF ERRNO = ERR_INOMAX THEN
            TPWrite "R2: WARNING - Max interrupts reached.";
        ELSEIF ERRNO = ERR_SIGSUPSEARCH THEN
            TPWrite "R2: ERROR - DI signal '" + DI_INTERRUPT_SIGNAL + "' not found!";
        ELSE
            TPWrite "R2: Interrupt setup error:" \Num:=ERRNO;
        ENDIF
    ENDPROC

    ! IDelete isolated so its error doesn't skip CONNECT/ISignalDI
    PROC Safe_IDelete_R2()
        IDelete ir_stop_trigger_R2;
    ERROR
        TRYNEXT;
    ENDPROC

    PROC KeepLooping()
        WHILE TRUE DO
            IF newTargetFlag_R2 = TRUE THEN
                newTargetFlag_R2 := FALSE;
                IF smIndx = "d" THEN
                    Run_Motion_Manager_R2;
                ELSEIF smIndx = "I" THEN
                    TPWrite "R2, ACK to client";
                ELSEIF smIndx = "T" THEN
                    TPWrite "R2, comm closed by client";
                ELSE
                    TPWrite "Invalid robot index." + smIndx;
                ENDIF

                executionNotCompleted_R2 := FALSE;
                TPWrite "R2, execution completed, waiting for next command.";
            ENDIF

            WaitTime 0.25;
        ENDWHILE
    ENDPROC

    ! ====================================================
    ! MOTION MANAGER
    ! ====================================================
    PROC Run_Motion_Manager_R2()
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

        ! Interrupt-aware sync: if the other robot was interrupted and
        ! ExitCycled, it will never reach this sync point. Skip to avoid deadlock.
        IF NOT wasInterrupted_R1 AND NOT wasInterrupted_R2 THEN
            WaitSyncTask syncEND, all_tasks;
        ELSE
            TPWrite "R2: Sync skipped - interrupt detected.";
        ENDIF

        TPWrite "R2: Motion completed successfully.";
    ENDPROC

    PROC executeState (num pathChoice, num stateChoice, absPointStruct tempPointStruct)
        VAR string stateChoiceString;
        VAR tooldata toolTemp;
        VAR wobjdata tempWobj;

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
        ENDTEST
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
    ! TRAP HANDLER - uses ExitCycle (RAISE cannot escape TRAP)
    ! ====================================================
    TRAP trap_handle_stop_R2
        TPWrite "R2: !!! TRAP TRIGGERED - DI Interrupt !!!";

        StopMove;
        ClearPath;
        StartMove;

        ! Set PERS flags before ExitCycle (commModule reads these)
        wasInterrupted_R2 := TRUE;
        executionNotCompleted_R2 := FALSE;

        ExitCycle;
    ENDTRAP

ENDMODULE
