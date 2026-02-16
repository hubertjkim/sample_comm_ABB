# PHASE 1: Interrupt-Driven Feedback (Global Eject)

**Status**: ✅ VALIDATED (2026-02-10)
**Goal**: Implement digital input interrupt inside the nested loop of RAPID script.
**Result**: ExitCycle approach with WaitSyncTask (replacing SyncMoveOn) confirmed working in RobotStudio.

---

## Requirements

### Digital Input Interrupt Behavior

**IMPORTANT: Unified Acknowledgment Protocol**

The system must implement a **unified acknowledgment** approach, NOT separate ACK_DONE and ACK_SKIPPED signals:

1. **When DI interrupt triggers from EITHER ROB1 or ROB2:**
   - The triggered robot immediately stops its current motion (via TRAP handler)
   - commModule waits for **BOTH ROB1 AND ROB2** to complete their current motion state
   - After both robots are idle/completed, commModule sends a **single acknowledgment** back to server_multimove.py → clientUI.py
   - The acknowledgment should be the same regardless of whether an interrupt occurred

2. **Synchronization Requirement:**
   - Since ROB1 and ROB2 operate as a coordinated multimove system, they must complete their motion sequences together
   - Even if only one robot is interrupted, the system waits for both to reach a safe idle state
   - This ensures coordination integrity and prevents desynchronization between the two robots

3. **Implementation Strategy:**
   - Use the "Global Eject" strategy from Gemini's suggestion
   - Both MainModule_ROB1 and MainModule_ROB2 must have TRAP handlers for their respective DI signals
   - commModule must track completion status of both robots before sending acknowledgment
   - Maintain decoupled architecture: communication logic stays in commModule, motion logic in MainModules

---

## Gemini's Original Suggestion (Global Eject via RAISE)

Using the TRAP function from RAPID, build an interrupt DI signal that exits the current motion as soon as the signal is detected. The entire structure remains the same, such that still robot controller and RAPID takes the incoming motion state information, but while execution, it exits the current motion upon the interrupt is trigger. While discussion with Gemini, we decided to go with "Global Eject" Strategy. This is the suggestion from Gemini, but the suggested script is not ideal as the socket communication functionality is not decoupled from the motion related scripts (such as MainModule_R1, MainModule_R2). Here is the excerpts of our conversation, primarily focusing on how to modify the RAPID scripts:

    If your architecture relies on deeply nested procedures (e.g., main → ProcessA → SubRoutineB → MoveFunction), using TRYNEXT becomes a nightmare because the error would only skip the smallest nested piece, not necessarily move your "state" forward to the next logical step.

    In a nested architecture, The Global Eject strategy is the most stable and predictable method. Instead of trying to "skip" one line, you "cancel" the entire active stack and reset to a known safe state.

    When you RAISE an error in a nested routine and that routine doesn't have an ERROR handler, RAPID "bubbles" the error up to the caller. By placing a single ERROR handler in your highest-level motion manager, you can catch an interrupt from anywhere in the nesting and force a jump to your Idle/Recovery logic.
    Here is the sample code from Gemini. But Gemini does not know the entire structures.
```rapid
        MODULE MainModule
            ! --- CONFIGURATION ---
            CONST errnum ERR_INTERRUPT := 99;
            VAR intnum ir_stop_trigger;

            ! --- MAIN LOOP (The "Idle" State) ---
            PROC main()
                ! 1. Setup Interrupt
                IDelete ir_stop_trigger;
                CONNECT ir_stop_trigger WITH trap_handle_stop;
                ISignalDI di_InputSignal, 1, ir_stop_trigger;

                WHILE TRUE DO
                    ! 2. WAIT (This IS your "Idle Function")
                    ! The robot sits here doing nothing until Python talks.
                    SocketReceive client_socket \Data:=received_data;

                    ! 3. EXECUTE
                    ! We wrap the motion in a manager procedure to handle the error bubbling
                    Run_Motion_Manager(received_data);

                    ! Loop immediately recycles to "SocketReceive" to wait for next object
                ENDWHILE
            ENDPROC

            ! --- THE MANAGER (Handles the Logic & Handshake) ---
            PROC Run_Motion_Manager(robtarget target_pos)
                ! Run your deep nested logic
                Execute_Complex_Sequence(target_pos);

                ! --- IF SUCCESSFUL ---
                ! This line only runs if no error occurred
                SocketSend client_socket \Str:="ACK_DONE";

            ERROR
                IF ERRNO = ERR_INTERRUPT THEN
                    ! --- IF INTERRUPTED ---
                    ! 1. Tell Python we are skipping this one
                    SocketSend client_socket \Str:="ACK_SKIPPED";

                    ! 2. Return to main() to wait for NEXT object
                    ! This cancels the rest of "Execute_Complex_Sequence"
                    RETURN;
                ENDIF
            ENDPROC

            ! --- THE NESTED LOGIC ---
            PROC Execute_Complex_Sequence(robtarget target)
                ! This can be as deep as you want
                Move_To_Approach();
                Move_To_Grip(target); ! <--- If interrupt hits here...
                Retract_Motion();
                ! ...The error bubbles up to Run_Motion_Manager
            ENDPROC

            ! --- THE TRAP (The Physical Stop) ---
            TRAP trap_handle_stop
                ! 1. Stop the motors immediately
                StopMove;

                ! 2. CLEAR PATH (Answering your Q3)
                ! This deletes the motion command that was executing.
                ! Without this, "StartMove" would try to finish the interrupted line.
                ClearPath;

                ! 3. Re-enable motion logic
                ! We must tell the controller "It's okay to move again later"
                StartMove;

                ! 4. Trigger the Logic Jump
                RAISE ERR_INTERRUPT;
            ENDTRAP
        ENDMODULE
```

---

## Implementation History

### Date: 2026-02-10 (Revised: ExitCycle Approach)
### Status: ✅ VALIDATED

#### RAISE Approach — Failed (2026-02-09 to 2026-02-10)

Gemini's suggested "Global Eject" strategy used `RAISE` from inside a TRAP handler to bubble an error up through the call chain to an ERROR handler. Systematic testing in RobotStudio confirmed this **cannot work**:

| Error Type | Result |
|-----------|--------|
| Custom error (BookErrNo) | Event 40229 "Unhandled error" — RAISE fires but no handler is reachable from TRAP context |
| Built-in error (ERR_ARGVALERR=1092) | Event 40199 "Illegal error number" — built-in errors are outside RAISE range (1-90) |
| With/without StopMove/ClearPath | Same failure — the motor sequence is not the cause |

**Root cause**: A TRAP routine runs in a separate execution context. `RAISE` inside a TRAP has no path to the interrupted routine's ERROR handlers. This is a fundamental RAPID limitation, not a configuration issue.

Test scripts preserved in `reference/TestInterrupt_R1.mod` and findings in `reference/discussion_w_gemini.md`.

#### ExitCycle Approach — Current Implementation (2026-02-10)

Instead of trying to bubble an error, `ExitCycle` terminates the entire execution cycle and restarts from `main()`. A PERS flag tells `main()` to skip initialization and go straight to the idle loop.

**How It Works:**
1. **Initialization** (fresh start only): `Setup_Interrupt_Rx()` connects DI signal to TRAP handler, `assignWaypoints`, `state_HOME`
2. **Normal Operation**: Motion executes via `Run_Motion_Manager_Rx()`, no ERROR wrappers needed
3. **Interrupt Triggered**:
   - DI signal fires → `trap_handle_stop_Rx` executes immediately
   - Physical stop: StopMove → ClearPath → StartMove
   - Set PERS flags: `wasInterrupted_Rx := TRUE`, `executionNotCompleted_Rx := FALSE`
   - `ExitCycle` → program restarts from main()
4. **Restart**: main() sees `wasInterrupted_Rx == TRUE` → skips assignWaypoints/state_HOME → goes to KeepLooping
5. **Unified Acknowledgment** (unchanged):
   - commModule waits for BOTH `executionNotCompleted_R1` and `_R2` to become FALSE
   - Logs interrupt status for diagnostics
   - Sends single unified `"ACK_DONE"` to clientUI.py
   - Resets wasInterrupted flags for next cycle

**Key Design Decisions:**
- `ExitCycle` clears interrupt connections → must re-run IDelete/CONNECT/ISignalDI on every main() restart
- `IDelete` isolated in its own `Safe_IDelete_Rx()` proc with `ERROR TRYNEXT` to avoid skipping CONNECT/ISignalDI
- No BookErrNo, no ERROR relay handlers, no safety-net ERROR handlers needed — ExitCycle bypasses the entire call chain
- **Interrupt-aware WaitSyncTask**: Both `Run_Motion_Manager_R1` and `_R2` check `wasInterrupted_R1` and `wasInterrupted_R2` before entering `WaitSyncTask`. If either robot was interrupted and ExitCycled, it will never reach the sync point — the other robot must skip sync to avoid deadlock.
- **SyncMoveOn incompatible with ExitCycle interrupt**: During `SyncMoveOn` coordinated motion (`\ID` moves), one robot's ExitCycle leaves the other robot's motion instruction permanently stuck at the motion planner level. `SyncMoveUndo` only exits sync mode for the calling task — it does NOT release the other robot. The blocked robot may not even process DI interrupts while stuck in the motion planner. **Solution**: Replace `SyncMoveOn`/`SyncMoveOff`/`\ID` with `WaitSyncTask` + independent moves for any motion that needs to be interruptible. This trades path-coordinated motion for task-level synchronization at start/end points.
- **Cross-task PERS**: Each MainModule declares the other robot's `wasInterrupted` flag as PERS for the WaitSyncTask check (R1 declares `wasInterrupted_R2`, R2 declares `wasInterrupted_R1`)
- **wasInterrupted flag reset guarantee**: commModule resets `wasInterrupted_R1` and `_R2` to FALSE in three places: (1) `commMain()` startup, (2) "I" handshake handler, (3) after ACK_DONE is sent. This ensures flags are clean for the next DI interrupt cycle regardless of how the system enters its current state.

---

## Files Modified

**1. MainModule_ROB1.mod** (`/ABB RAPID/MainModule_ROB1.mod`)
- `main()`: Checks `wasInterrupted_R1` to skip init on ExitCycle restart
- `Setup_Interrupt_R1()`: Uses `Safe_IDelete_R1()`, always re-configures (no caching)
- `Safe_IDelete_R1()`: New helper proc with `ERROR TRYNEXT`
- `trap_handle_stop_R1`: StopMove → ClearPath → StartMove → set flags → ExitCycle
- `Run_Motion_Manager_R1()`: Interrupt-aware WaitSyncTask (checks both wasInterrupted flags before sync)
- Added `PERS bool wasInterrupted_R2` for cross-task sync check
- Removed: `VAR errnum`, `BookErrNo`, all `ERROR` handlers for interrupt, `ERROR RAISE` relay in executeState

**2. MainModule_ROB2.mod** (`/ABB RAPID/MainModule_ROB2.mod`)
- Identical changes mirrored with R2 naming
- Added `PERS bool wasInterrupted_R1` for cross-task sync check

**3. commModule.mod** (`/ABB RAPID/commModule.mod`)
- `commMain()`: Resets `wasInterrupted_R1` and `_R2` to FALSE at startup
- `updateGlobalVariable()` CASE "I": Resets both flags on client handshake
- Existing post-ACK_DONE reset (lines 119-120) retained for normal cycle cleanup

---

## Architecture Integrity
- **Decoupling Maintained**: Communication logic in commModule, motion logic in MainModules
- **Synchronization**: commModule waits for both ROB1 and ROB2 before ACK
- **Unified Acknowledgment**: Single ACK_DONE regardless of interrupt status
- **Backward Compatible**: No Python changes required
- **Simpler**: No BookErrNo, no ERROR relay chain, no safety-net handlers

---

## Configuration Required
Configure DI signal name in both MainModule files:
```rapid
CONST string DI_INTERRUPT_SIGNAL := "diInterruptSignal";
```

---

## Testing Checklist
- [x] Configure DI signal name in both MainModule files (default: "diInterruptSignal")
- [x] Load modified modules into robot controller (T_ROB1, T_ROB2, T_COMM tasks)
- [x] **Test 1 - Normal Operation**: Execute motion without interrupt → ACK_DONE received
- [x] **Test 2 - ROB1 Interrupt**: Trigger DI → both robots stop, ExitCycle restart, ACK_DONE received, next command works
- [x] **Test 3 - SyncMoveOn deadlock**: Confirmed — replaced with WaitSyncTask + independent moves
- [x] **Test 4 - Final validation**: WaitSyncTask with interrupt-aware skip works correctly

---

## Lessons Learned
1. **RAISE cannot escape TRAP** — fundamental RAPID limitation, not configuration
2. **ExitCycle is the correct escape mechanism** — terminates cycle, restarts from main()
3. **ExitCycle clears interrupt connections** — must always re-setup with Safe_IDelete pattern
4. **SyncMoveOn is incompatible with ExitCycle interrupt** — motion planner coupling can't be broken from one side. SyncMoveUndo only frees calling task (Event 41633 restricts it to UNDO handlers anyway)
5. **WaitSyncTask + independent moves** is the correct pattern for interruptible multi-robot motion
6. **Interrupt-aware WaitSyncTask** — check wasInterrupted flags before every WaitSyncTask to prevent barrier deadlock
