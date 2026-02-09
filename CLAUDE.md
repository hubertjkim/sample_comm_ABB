# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
**Always check `ACTIVE_PHASE` in CLAUDE.md before making changes.**
**Always update CLAUDE.md before making changes.**


**CURRENT STATUS**: PHASE 1 implementation revised (2026-02-09). Pending user verification.
**NEXT PHASE**: PHASE 2 (awaiting PHASE 1 verification/validation)

## Project Overview

This is a Handshake Platform between Python and ABB RobotStudio involving **THREE robots** across **TWO robot controllers**:

### System Architecture

**Client Layer:**
- `clientUI.py`: Main user interface that interacts with operators. Creates a linked list of tasks and sends data to virtual servers via ZMQ.

**Server Layer (Virtual Servers):**
- `server_multimove.py`: Virtual server communicating with **ONE robot controller** that controls **TWO robots (ROB1 and ROB2)** in synchronized multimove operation. This corresponds to the "/ABB RAPID" folder scripts.
- `server_cobot.py`: Virtual server communicating with a **separate independent robot controller** for **ROB3** (a cobot). This is not part of the "/ABB RAPID" folder scope.

**Robot Controller Layer:**
- **Multimove Controller** (ROB1 + ROB2): Contains three RAPID modules running as separate tasks:
  - `commModule.mod` (T_COMM task): Handles all socket communication with server_multimove.py
  - `MainModule_ROB1.mod` (T_ROB1 task): Motion control for Robot 1
  - `MainModule_ROB2.mod` (T_ROB2 task): Motion control for Robot 2
- **Cobot Controller** (ROB3): Independent controller (not detailed in this project scope)

## Phased Development Strategy

### PHASE 1 (PENDING_VERIFICATION): Interrupt-driven feedback for the ROBOT
- **Goal**: Implement the digital input interrupt inside the nested loop of RAPID script.
- **Action**: Given the RAPID script, you are to modify it accordingly with all the context you have.
- **Status**: ⏳ Implementation revised on 2026-02-09 - Awaiting user verification
### PHASE 2 (Future_PHASE): Enable Streaming feature.(pyton)
- **Goal**: Use the "The Leaky Bucket" architecture for data streaming between python script and ABB RAPID code.
- **Action**: Create a sample python code for handshaking such that, PHASE 3 can use this to accomplish the handshake.
- **Restriction**: My current ABB RobotStudio can't use egm(external-guided-motion, that allows for ~4ms streaming data transfer). The socket 
### PHASE 3 (Future_PHASE): Enable ROS2 (windows11 but using the docker via wsl2) to replace python. 
- **Goal**: Finalize the handshake platform work between ROS2 and RobotStudio.
- **Action**: Apply the sample from PHASE 2, "The Leaky Bucket" algorithm using circular buffer into the existing algorithm, and expands it into ROS2 node. 
- **Restriction**: My environment can't support dual boot. Always docker with wsl2 is the only option. 

## Detailed Script Architecture

### Python Scripts

**1. clientUI.py** - Main User Interface
- Interacts with the operator
- Creates a linked list of tasks from operator input
- Sends task sequences to virtual servers via ZMQ
- Receives acknowledgments from servers

**2. server_multimove.py** - Virtual Server for Multimove Controller
- Receives data packages from clientUI.py via ZMQ
- Communicates with the **Multimove Robot Controller** (ROB1 + ROB2) via TCP/IP socket
- Benefits: Easy addition of more controllers, easy IP swapping between real/virtual controllers in RobotStudio

**3. server_cobot.py** - Virtual Server for Cobot Controller
- Receives data packages from clientUI.py via ZMQ
- Communicates with the **independent Cobot Controller** (ROB3) via TCP/IP socket
- (Not part of the "/ABB RAPID" folder scope)

### ABB RAPID Scripts (Multimove Controller Only)

**Directory:** `~/ABB RAPID/` contains three .mod files for the Multimove Controller:

**1. commModule.mod** (T_COMM task)
- Dedicated communication task
- Constantly listens for packages from server_multimove.py via socket
- Parses incoming data packages
- Routes data to MainModule_ROB1 or MainModule_ROB2 as appropriate
- Sends acknowledgments back to server_multimove.py

**2. MainModule_ROB1.mod** (T_ROB1 task)
- Dedicated motion control task for Robot 1
- Receives motion commands from commModule via shared PERS variables
- Executes motion sequences for ROB1

**3. MainModule_ROB2.mod** (T_ROB2 task)
- Dedicated motion control task for Robot 2
- Receives motion commands from commModule via shared PERS variables
- Executes motion sequences for ROB2

**Key Architectural Points:**
- TASKs do NOT share namespace (functions, variables) unless universally declared as PERS
- The Multimove Controller has a **multimove license**, allowing all three modules to run within the same controller and synchronize
- Communication is **decoupled** from motion: commModule handles all socket I/O, MainModules handle all robot motion 



## Phase-Specific Restrictions
***Please make sure not to move ahead, unless the current stage is fully completed.***

**PHASE 1 (ACTIVE_PHASE)**
- Using the TRAP function from RAPID, I want to build an interrupt DI signal that exits the current motion as soon as the signal is detected. 
The entire structure remains the same, such that still robot controller and RAPID takes the incoming motion state information, but while execution, it exits the current motion upon the interrupt is trigger.
While discussion with Gemini, we decided to go with "Global Eject" Strategy. This is the suggestion from Gemini, but the suggested script is not ideal as the socket communication functionality is not decoupled from the motion related scripts (such as MainModule_R1, MainModule_R2). Here is the excerpts of our conversation, primarily focusing on how to modify the RAPID scripts: 

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

## PHASE 1 - CRITICAL REQUIREMENTS

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

## PHASE 1 - IMPLEMENTATION HISTORY

### Date: 2026-02-09 (Revised)
### Status: ⏳ AWAITING USER VERIFICATION

#### Implementation Summary
Successfully implemented the "Global Eject" interrupt strategy across all RAPID modules with decoupled architecture and unified acknowledgment protocol:

**Revisions Completed:**
1. ✅ Implemented unified acknowledgment (single ACK_DONE message regardless of interrupt status)
2. ✅ Confirmed synchronization logic waits for BOTH ROB1 and ROB2 to complete before acknowledgment
3. ✅ Updated system architecture documentation (added ROB3/server_cobot.py context)

#### Files Modified

**1. MainModule_ROB1.mod** (`/ABB RAPID/MainModule_ROB1.mod`)
- Added interrupt configuration constants:
  - `ERR_INTERRUPT := 99` (custom error code)
  - `DI_INTERRUPT_SIGNAL` (configurable DI signal name)
  - `ir_stop_trigger_R1` (interrupt trigger variable)
  - `wasInterrupted_R1` (PERS flag shared with commModule)

- Created `Setup_Interrupt_R1()` procedure:
  - Initializes interrupt system with IDelete/CONNECT/ISignalDI
  - Includes error handling for common setup issues (ERR_INOMAX, ERR_SIGSUPSEARCH)

- Created `Run_Motion_Manager_R1()` procedure:
  - Wraps existing motion execution with ERROR handler
  - Implements Global Eject pattern: catches ERR_INTERRUPT → sets wasInterrupted_R1 → RETURNs cleanly
  - Resets interrupt flag at start of each motion sequence

- Created `trap_handle_stop_R1` TRAP handler:
  - Physical interrupt service routine triggered by DI signal
  - Sequence: StopMove → ClearPath → StartMove → RAISE ERR_INTERRUPT
  - Enables immediate motor stop and clean path clearing

- Modified `KeepLooping()` procedure:
  - Integrated Run_Motion_Manager_R1 call for motion execution
  - Added conditional execution flag reset (only if not interrupted)

**2. MainModule_ROB2.mod** (`/ABB RAPID/MainModule_ROB2.mod`)
- Applied identical interrupt implementation as R1 (R2-specific naming)
- All components mirrored: Setup_Interrupt_R2, Run_Motion_Manager_R2, trap_handle_stop_R2
- Maintains symmetry for dual-robot multimove operation

**3. commModule.mod** (`/ABB RAPID/commModule.mod`)
- Added PERS declarations for interrupt status:
  - `wasInterrupted_R1` and `wasInterrupted_R2` flags (shared with MainModules)

- ✅ **REVISED:** Unified acknowledgment protocol in `cmdExe()`:
  - ✅ Waits for BOTH ROB1 and ROB2 to complete (via `WHILE executionNotCompleted_R1 OR executionNotCompleted_R2` loop)
  - ✅ Sends single unified `"ACK_DONE"` message regardless of interrupt status
  - ✅ Logs interrupt status for diagnostics before sending acknowledgment
  - ✅ Resets interrupt flags after acknowledgment for next cycle

#### Architecture Integrity
✅ **Decoupling Maintained**: Communication logic remains in commModule, motion logic in MainModules
✅ **Synchronization Implemented**: commModule waits for both ROB1 and ROB2 before acknowledgment
✅ **Unified Acknowledgment**: Single ACK_DONE message sent regardless of interrupt status
✅ **Multimove Compatibility**: Both robots independently handle interrupts, flags tracked separately
✅ **No Python Changes Required**: Backward compatible - clientUI.py receives ACK_DONE as before

#### Configuration Required Before Use
⚠️ **CRITICAL**: Configure DI signal name in both MainModule files:
```rapid
CONST string DI_INTERRUPT_SIGNAL := "diInterruptSignal";
```
Replace with actual signal name from I/O System Configuration (e.g., "diEmergencyStop", "diSafetyStop")

#### How It Works (Revised Implementation - Awaiting Verification)
1. **Initialization**: `Setup_Interrupt_Rx()` connects DI signal to TRAP handler at startup
2. **Normal Operation**: Motion executes via `Run_Motion_Manager_Rx()` with ERROR protection
3. **Interrupt Triggered**:
   - DI signal fires → `trap_handle_stop_Rx` executes immediately
   - Physical stop: StopMove → ClearPath → StartMove
   - Logic jump: RAISE ERR_INTERRUPT
4. **Error Bubbling**: ERR_INTERRUPT caught by Run_Motion_Manager_Rx ERROR handler
5. **Clean Exit**: Sets wasInterrupted flag, resets execution flag, RETURNs to idle
6. ✅ **Unified Acknowledgment**:
   - commModule waits for BOTH `executionNotCompleted_R1` and `executionNotCompleted_R2` to become FALSE
   - Logs interrupt status for diagnostics (R1 and R2 interrupt flags)
   - Sends single unified `"ACK_DONE"` acknowledgment to clientUI.py
   - Resets interrupt flags for next cycle

#### Testing Checklist
- [ ] Configure DI signal name in both MainModule files (default: "diInterruptSignal")
- [ ] Load modified modules into robot controller (T_ROB1, T_ROB2, T_COMM tasks)
- [ ] **Test 1 - Normal Operation**: Execute motion without interrupt
  - [ ] Verify both robots complete motion successfully
  - [ ] Verify clientUI.py receives "ACK_DONE"
  - [ ] Check FlexPendant logs show "Motion completed successfully"
- [ ] **Test 2 - ROB1 Interrupt**: Trigger DI signal on ROB1 during motion
  - [ ] Verify ROB1 stops immediately and executes TRAP handler
  - [ ] Verify commModule waits for BOTH ROB1 and ROB2 to complete
  - [ ] Verify clientUI.py receives unified "ACK_DONE" (not separate signal)
  - [ ] Check FlexPendant logs show interrupt status for diagnostics
  - [ ] Verify robot accepts next command immediately
- [ ] **Test 3 - ROB2 Interrupt**: Trigger DI signal on ROB2 during motion
  - [ ] Verify ROB2 stops immediately and executes TRAP handler
  - [ ] Verify commModule waits for BOTH ROB1 and ROB2 to complete
  - [ ] Verify clientUI.py receives unified "ACK_DONE"
  - [ ] Check FlexPendant logs show interrupt status for diagnostics
  - [ ] Verify robot accepts next command immediately
- [ ] **Test 4 - Dual Interrupt**: Trigger DI signals on both robots simultaneously
  - [ ] Verify both robots stop and handle interrupts
  - [ ] Verify unified acknowledgment sent only once
  - [ ] Verify system recovers and accepts next command

#### Next Phase
PHASE 2 preparation requires PHASE 1 interrupt system to be fully tested, verified, and operational in production environment.

---

**PHASE 2 (Future)**
- I want to have a different mode for each robot for individual switch from pre-define state motion to streaming mode. During the streaming mode, it only takes the 6 joint motions as input. Here is the conversation from the Gemini. 

    Since you do not have the EGM (Externally Guided Motion) option, you are entering the realm of "standard socket streaming." This is challenging because the RAPID interpreter is not designed for real-time 30 Hz updates like a joystick. If the robot finishes a move before the next one arrives and is processed, it must stop (stutter). If you buffer too many points, the robot moves smoothly but the camera feedback is old (latency).

    Here is the architectural blueprint to achieve ~30 Hz (or close to it) visual servoing without EGM using a Producer-Consumer model.
    1. The Architecture: "The Leaky Bucket"

    You need to decouple the communication (receiving data) from the motion (executing moves). You mentioned you already have a background communication script—this is your "Producer." Your main motion loop is the "Consumer."

        Global Variable (The Bucket): A shared array (or circular buffer) of robtargets between the background and main task.

        Producer (Background): Reads from the socket as fast as possible. If a new packet arrives, it puts it into the buffer.

        Consumer (Motion): Peeks at the buffer. If there are points available, it executes a MoveL with a Zone (blending radius).

    2. Synchronization: The "Pre-fetch" Strategy

    You cannot strictly "clock" the robot to 30 Hz. Instead, you synchronize by managing the Buffer Level.

        ROS 2 (Sender): Sends pose updates at a fixed rate (e.g., 30 Hz).

        RAPID (Receiver):

            Startup: Wait until the buffer has N points (e.g., 5 points) before starting the first move. This is your "safety margin" against stuttering.

            Running: The robot executes MoveL. Because you use a blending zone (e.g., z1 or z5), the robot's "Lookahead" feature will peek at the next instruction while executing the current one.

    3. The Trade-off: Latency vs. Stuttering

    This trade-off is controlled entirely by two variables: Buffer Length and Zone Size.
    For Low Latency, buffer size 1-2 points, Zone is z0 / fine, Result is "High Stutter Risk. Robot moves to point A, stops, asks ""what's next?"", then moves to B. Movement is jerky."
    For Smooth Motion, buffer size 10+ points, Zone is z10 / z50, Result is High Latency. The robot is executing a point received 300ms ago. Visual servoing will oscillate or overshoot.
    For The Sweet Spot, buffer size 3-5 points, Zone is z1 - z5, Result is Robot blends corners smoothly. Latency is manageable (~100-150ms).

    4. Implementation Steps
    You need to create a Circular Buffer in your robot controller. This acts as a shock absorber between your Python script and the robot's physical motors.

    A. The Shared, Global Data (Global Module)

    Create a PERS (Persistent) global array accessible by both tasks. Create a new module (or add to your existing SYSMODULE) to hold the buffer. It must be PERS so both the Background (Receiver) and Main (Motion) tasks can see it.

```RAPID
        MODULE SharedData(SYSMODULE)
            ! --- CONFIGURATION ---
            CONST num BUF_SIZE := 50;  ! Size of the buffer
            
            ! --- SHARED VARIABLES ---
            ! The buffer itself (Cartesian Targets)
            PERS robtarget stream_buffer{BUF_SIZE}; 
            
            ! Pointers to track position
            PERS num write_ptr := 1;   ! Where the Background task puts data
            PERS num read_ptr := 1;    ! Where the Motion task takes data
            
            ! Flags
            PERS bool is_streaming := FALSE;  ! Master switch for the mode
        ENDMODULE
```
    B. The Background Task (Producer/Receiver)

    This task does nothing but shovel data from the socket to the array. This task stays in a loop. It looks at the incoming data header to decide if it's a "Standard Package" or a "Stream Point."

```RAPID    
        PROC Background_Communication()
        VAR string receive_string;
        VAR robtarget temp_target;
        VAR bool ok;

        WHILE TRUE DO
            ! Wait for data from Python
            SocketReceive client_socket \Str:=receive_string;

            ! Check if this is a command to START streaming or a DATA packet
            IF receive_string = "START_STREAM" THEN
                is_streaming := TRUE;
                write_ptr := 1;
                read_ptr := 1;
                
            ELSEIF is_streaming = TRUE THEN
                ! --- FAST LANE: STREAMING MODE ---
                ! Parse string into X,Y,Z,q1,q2,q3,q4
                ok := StrToVal(receive_string, temp_target);
                
                ! Add to Buffer
                stream_buffer{write_ptr} := temp_target;
                
                ! Advance Write Pointer (Circular Logic)
                write_ptr := write_ptr + 1;
                IF write_ptr > BUF_SIZE THEN
                    write_ptr := 1;
                ENDIF
                
            ELSE
                ! --- SLOW LANE: STANDARD MODE ---
                ! Your existing logic for standard packages goes here
            ENDIF
        ENDWHILE
    ENDPROC
```

    C. The Main Motion Task (Consumer/Motion Executer)

    This is where the magic happens. You use MoveL with a zone to prevent stopping. This task waits for the buffer to fill slightly, then moves.

```RAPID    
        PROC Main_Motion()
            VAR num points_available;
            
            WHILE TRUE DO
                IF is_streaming = TRUE THEN
                    ! Calculate how many points are in the buffer
                    IF write_ptr >= read_ptr THEN
                        points_available := write_ptr - read_ptr;
                    ELSE
                        points_available := (BUF_SIZE - read_ptr) + write_ptr;
                    ENDIF

                    ! --- TUNING PARAMETERS ---
                    ! 1. Anti-Starvation: Wait for 3 points before moving
                    IF points_available > 3 THEN
                        ! 2. The Move: Use Zone (z5) to blend!
                        ! \V := 100% of speed, adjust z5/z10 for smoothness
                        MoveL stream_buffer{read_ptr}, vMax, z5, tool0;
                        
                        ! Advance Read Pointer
                        read_ptr := read_ptr + 1;
                        IF read_ptr > BUF_SIZE THEN
                            read_ptr := 1;
                        ENDIF
                    ELSE
                        ! Buffer empty? Wait a tiny bit to save CPU
                        WaitTime 0.005;
                    ENDIF
                    
                ELSE
                    ! Your existing Standard Mode logic
                    WaitTime 0.1;
                ENDIF
            ENDWHILE
        ENDPROC
```
    D. Python GUI Implementation (The Simulator)

    In your Python GUI, create a button or function called Test_Streaming. This will mimic what ROS 2 will eventually do.

```python
    import socket
    import time
    import math

    def run_streaming_test(sock):
        # 1. Send Handshake to switch robot to Streaming Mode
        sock.sendall(b"START_STREAM")
        time.sleep(0.5) # Give RAPID time to reset pointers

        print("Starting 30Hz Stream...")
        
        # 2. Loop to generate a Sine Wave motion (Simulating a camera tracking)
        t = 0
        frequency = 30.0 # Target 30 Hz
        period = 1.0 / frequency
        
        try:
            while True:
                start_time = time.time()
                
                # Generate a fake coordinate (e.g., moving in a circle)
                x = 300 + 50 * math.sin(t)
                y = 0 + 50 * math.cos(t)
                z = 400
                
                # Format as RAPID string (example format)
                # "[x,y,z],[q1,q2,q3,q4],..."
                # Note: Ensure your RAPID StrToVal can parse this format!
                msg = f"[[{x:.2f},{y:.2f},{z:.2f}],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]"
                
                sock.sendall(msg.encode())
                
                t += 0.1
                
                # 3. Maintain 30Hz timing
                elapsed = time.time() - start_time
                sleep_time = period - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            print("Stopping Stream")

```
    5. Critical Tips for 30 Hz Success

    Filter Small Moves: In your ROS 2 node, before sending a point, check the distance from the previous point. If the robot moves only 0.1mm, do not send it. The RAPID interpreter takes time to process every instruction (approx 3-10ms). If you flood it with microscopic moves, the interpreter will lag behind reality.

    ROS 2 Rate Limiting: Ensure your ROS 2 node publishes at a strict rate. If it bursts (sends 10 points in 1ms), your buffer fills up instantly, increasing latency.

    Use \Conc? You might see advice to use the \Conc (Concurrent) switch in MoveL. For this specific buffer setup, it is usually not necessary because the Zone (z5) already handles the lookahead.

    Tuning Latency: Start with a buffer "start threshold" of 5 points. Slowly decrease it (4, 3, 2) until you see the robot physically jerk/stop. Then add 1 back. That is your minimum latency floor.

    Once you have this running, you will see one of two problems. Here is how to fix them:

    Problem A: The Robot Stutters (Jerky motion)

        Cause: The robot eats the points faster than Python sends them. The buffer hits 0, and the robot stops to wait.

        Fix 1: Increase the "Anti-Starvation" threshold in RAPID (change IF points_available > 3 to > 5).

        Fix 2: Increase the Zone size (change z5 to z10 or z20). This makes the robot "cut corners" more aggressively, keeping speed up.

    Problem B: The Robot lags behind (High Latency)

        Cause: You have too many points buffered. You are seeing what Python sent 1 second ago.

        Fix: Decrease the "Anti-Starvation" threshold (change > 5 to > 2).

    Integration with Feature 1 (The Interrupt)

    The beauty of this separation is that your Interrupt Trap (Feature 1) works perfectly here. If you trigger the DI signal while in Main_Motion loop:

        The TRAP triggers.

        StopMove executes.

        The loop breaks.

        You can then set is_streaming := FALSE in your error handler to force the system back to a safe state.

**PHASE 3 (Future)**
- For this modification, I am thinking of switching the current python interface to ros2 running in my container. The previous features remain the same, but during the streaming mode, ros2 controls the robot motion with external cameras, providing the 6 dofs to RAPID. 

