# PHASE 1

## How the Unified Acknowledgment Works

  Normal Operation:
  1. Both ROB1 and ROB2 execute motion
  2. Both complete successfully
  3. commModule sends unified "ACK_DONE"

  Interrupt Scenario (e.g., DI signal on ROB1):
  1. ROB1's TRAP handler triggers → StopMove → ClearPath → StartMove → sets
  wasInterrupted_R1 = TRUE + executionNotCompleted_R1 = FALSE
  2. ROB2 continues and completes normally → sets executionNotCompleted_R2 = FALSE
  3. commModule's WHILE loop exits when BOTH executionNotCompleted_R1 and
  executionNotCompleted_R2 are FALSE
  4. commModule logs: "Motion interrupted (R1: TRUE, R2: FALSE)" for diagnostics
  5. commModule sends same unified "ACK_DONE" message
  6. System is ready for next command


# PHASE 2

## Changes Made                                                                                         
  1. commModule.mod - Communication layer                                                 
  - Extended dataPacket RECORD with streamJ1-streamJ6 fields
  - Added PERS variables: operationMode, streamJointTarget_R1, newStreamTarget_R1
  - Updated ParseMessage to parse "j;j1;j2;j3;j4;j5;j6;" format
  - Updated updateGlobalVariable "j" case to populate the joint target and set streaming
  flag
  - Modified cmdExe dispatch: "j" mode triggers R1 only, "d" mode works as before

  2. MainModule_ROB1.mod - R1 motion
  - Added PERS declarations for operationMode, streamJointTarget_R1, newStreamTarget_R1
  - Updated KeepLooping to check newStreamTarget_R1 independently of newTargetFlag_R1
  - Added Run_Joint_Stream_R1 procedure: executes MoveAbsJ with z5 zone, protected by
  Global Eject error handler

  3. MainModule_ROB2.mod - R2 compatibility
  - Added PERS string operationMode for cross-task PERS compatibility (no motion changes)

  4. server_multiMove.py - Python side
  - Added send_joint_stream(): sends j; prefixed joint values, waits for ACK
  - Added run_streaming_test(): 20-point sine wave on J1 (+/- 5 deg, 2 Hz)
  - Integrated dispatch: data[0]==5 for single joint stream, data[0]==6 for test sequence

  5. CLAUDE.md - Updated phase statuses and added implementation history

  Next Steps

  - Verify in RobotStudio (testing checklist in CLAUDE.md)
  - After validation, implement the circular buffer for continuous streaming without
  per-point ACK wait
  
  
  
In RAPID, RAISE from a TRAP does not auto-bubble at all. 
  The error lands in the exact routine that was executing the motion instruction, and if  
  that routine has no ERROR handler, it's immediately "unhandled" — full stop, no further 
  propagation.                                                                          
                                                                                          
  So every routine in the call chain between the motion instruction and Run_Motion_Manager
   needs ERROR RAISE;. The relay chain must be unbroken:                                  
                                                                                          
  TRAP → RAISE                                                                            
    → customMove():  ERROR RAISE;    ← catches, re-raises to caller                       
    → state_STANDBY(): ERROR RAISE;  ← catches, re-raises to caller
    → executeState():  ERROR RAISE;  ← catches, re-raises to caller  (already done)
    → Run_Motion_Manager_R1(): catches ERR_INTERRUPT_R1, handles it

  Every routine that directly contains a motion instruction (MoveJ, MoveL, MoveAbsJ, etc.)
   or calls another routine that does, needs the ERROR RAISE; relay.

======================================================



Current RAISE Approach (what we wanted)                                                 
   
  DI fires → TRAP → RAISE → ERROR handler in Run_Motion_Manager_R1                        
    → sets wasInterrupted_R1 := TRUE                                                    
    → sets executionNotCompleted_R1 := FALSE                                           
    → RETURN                                                                          
    → back in KeepLooping (idle, WHILE TRUE, waiting for next newTargetFlag_R1)
    → commModule sees executionNotCompleted_R1 == FALSE → sends ACK_DONE
    → Python gets ACK → sends next command → cycle continues

  ExitCycle Approach (same result)

  DI fires → TRAP → StopMove → ClearPath → StartMove
    → sets wasInterrupted_R1 := TRUE
    → sets executionNotCompleted_R1 := FALSE
    → ExitCycle
    → main() restarts
    → sees wasInterrupted_R1 == TRUE → skips init → jumps to KeepLooping
    → KeepLooping (idle, WHILE TRUE, waiting for next newTargetFlag_R1)
    → commModule sees executionNotCompleted_R1 == FALSE → sends ACK_DONE
    → Python gets ACK → sends next command → cycle continues

  From step 4 onward, the behavior is identical. The robot is idle in KeepLooping,
  commModule sends ACK_DONE, Python sends the next command. The only difference is how we
  got back to KeepLooping — error bubbling vs. ExitCycle restart.

  Here's what the production main() would look like:

  PROC main()
      IF wasInterrupted_R1 THEN
          ! ExitCycle restart — skip all init, go straight to idle
          TPWrite "R1: Restarted after interrupt";
          wasInterrupted_R1 := FALSE;
          KeepLooping;
      ENDIF

      ! Normal first-run path (only runs once)
      TPErase;
      TPWrite "R1: Main module started.";
      Setup_Interrupt_R1;
      assignWaypoints;
      ConfJ \Off;
      state_HOME;
      ConfJ \On;
      KeepLooping;
  ENDPROC

  And the simplified TRAP (no RAISE, no ERROR relay chain needed):

  TRAP trap_handle_stop_R1
      StopMove;
      ClearPath;
      StartMove;
      wasInterrupted_R1 := TRUE;
      executionNotCompleted_R1 := FALSE;
      ExitCycle;
  ENDTRAP

  What gets removed from the production code:
  - BookErrNo / VAR errnum ERR_INTERRUPT_R1 — no custom error needed
  - RAISE in TRAP — replaced by ExitCycle
  - ERROR RAISE; relay in executeState — no error to relay
  - ERROR IF ERRNO = ERR_INTERRUPT_R1 in Run_Motion_Manager_R1 — no error to catch
  - ERROR ... TRYNEXT safety net in KeepLooping — ExitCycle bypasses it entirely

===================================
Function usage
  ┌────────────────────────────┬─────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │          Function          │      Location       │                                                         Usage                                                         │
  ├────────────────────────────┼─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ send_joint_stream()        │ server_multiMove.py │ Called automatically by main loop when elen == 6. Sends j; prefix to RAPID, waits for ACK_DONE.                       │
  ├────────────────────────────┼─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ run_streaming_test()       │ server_multiMove.py │ Standalone utility — communicates directly with RAPID via TCP/IP (bypasses ZMQ). For direct testing without clientUI. │
  ├────────────────────────────┼─────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Streaming test in clientUI │ clientUI.py         │ Full-pipeline test — sends 20 points through ZMQ → server_multiMove → RAPID. Use 's' then 'test' from the UI.         │
  └────────────────────────────┴─────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  RAPID code changes

  Not needed. The two protocol layers are independent:
  - ZMQ layer (clientUI ↔ server_multiMove): dispatched by elen — this is where the change happened
  - TCP/IP layer (server_multiMove ↔ commModule): dispatched by header character ("d", "j", "I", "T") — unchanged

  server_multiMove translates between them: elen==6 → send_data(joints, 'j;') → RAPID receives j;j1;j2;.... The commModule ParseMessage, updateGlobalVariable, and cmdExe already handle
   "j" correctly from the first draft.
