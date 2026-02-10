MODULE TestInterrupt_R1

    ! ====================================================
    ! TEST: ExitCycle from TRAP
    ! ====================================================
    ! Since RAISE cannot escape a TRAP (confirmed),
    ! use ExitCycle to restart from main() instead.
    !
    ! Flow:
    !   DI fires -> TRAP -> StopMove -> ClearPath ->
    !   StartMove -> set flag -> ExitCycle -> main()
    !
    ! main() checks the flag to know it was an interrupt
    ! restart (skips re-init, goes straight to idle loop).
    ! ====================================================

    CONST string DI_SIGNAL := "diInterruptSignal";

    VAR intnum ir_test;
    PERS bool wasInterrupted := FALSE;


    CONST jointtarget jtA := [[0, 0, 0, 0, 30, 0], [9E9,9E9,9E9,9E9,9E9,9E9]];
    CONST jointtarget jtB := [[10, 0, 0, 0, 30, 0], [9E9,9E9,9E9,9E9,9E9,9E9]];

    PROC main()
        TPErase;

        IF wasInterrupted THEN
            TPWrite "=== RESTARTED AFTER INTERRUPT ===";
            wasInterrupted := FALSE;
        ELSE
            TPWrite "=== FRESH START ===";
        ENDIF

        Setup_Interrupt;
        Motion_Loop;
    ENDPROC

    ! ====================================================
    ! INTERRUPT SETUP
    ! ====================================================
    PROC Setup_Interrupt()
        Safe_IDelete;
        CONNECT ir_test WITH trap_stop;
        ISignalDI DI_SIGNAL, 1, ir_test;
        TPWrite "Interrupt configured on: " + DI_SIGNAL;

    ERROR
        IF ERRNO = ERR_SIGSUPSEARCH THEN
            TPWrite "ERROR: Signal '" + DI_SIGNAL + "' not found!";
        ELSE
            TPWrite "Setup error:" \Num:=ERRNO;
        ENDIF
    ENDPROC

    ! ====================================================
    ! MOTION LOOP
    ! ====================================================
    PROC Motion_Loop()
        VAR num cycle := 0;

        WHILE cycle < 10 DO
            cycle := cycle + 1;
            TPWrite "--- Cycle " + NumToStr(cycle, 0) + " ---";

            TPWrite "Moving to A...";
            MoveAbsJ jtA, v100, fine, tool0;

            TPWrite "Moving to B...";
            MoveAbsJ jtB, v100, fine, tool0;

            TPWrite "Cycle " + NumToStr(cycle, 0) + " complete";
            WaitTime 1;
        ENDWHILE

        TPWrite "All 10 cycles done.";
    ENDPROC

    ! ====================================================
    ! TRAP HANDLER - uses ExitCycle instead of RAISE
    ! ====================================================
    TRAP trap_stop
        TPWrite "TRAP: DI triggered";
        StopMove;
        TPWrite "TRAP: StopMove done";
        ClearPath;
        TPWrite "TRAP: ClearPath done";
        StartMove;
        TPWrite "TRAP: StartMove done";
        wasInterrupted := TRUE;
        TPWrite "TRAP: ExitCycle...";
        ExitCycle;
    ENDTRAP

    ! ====================================================
    ! SAFE HELPER
    ! ====================================================
    PROC Safe_IDelete()
        IDelete ir_test;
    ERROR
        TRYNEXT;
    ENDPROC

ENDMODULE
