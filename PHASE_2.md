# PHASE 2: Enable Streaming Feature (Python + RAPID)

**Status**: ⏳ First draft implemented (2026-02-09). Single-point joint streaming for ROB1 only. Circular buffer iteration pending.
**Goal**: Use the "Leaky Bucket" architecture for data streaming between Python and ABB RAPID code.
**Restriction**: Current ABB RobotStudio can't use EGM (External Guided Motion, ~4ms streaming). Socket-based streaming only.
**Next Step**: Verification in RobotStudio

---

## Implementation History

### Date: 2026-02-09 (First Draft)
### Status: ⏳ AWAITING USER VERIFICATION

#### Implementation Summary
First draft of joint streaming: establishes data structures, two-layer protocol dispatch, mode toggling, and single-point `MoveAbsJ` execution for ROB1 only. The full circular buffer ("Leaky Bucket") will be layered on top in a subsequent iteration.

---

## Two-Layer Protocol Architecture

The system has two independent protocol layers. Mode switching happens at the ZMQ layer; the TCP/IP layer is header-driven and unchanged.

**Layer 1: ZMQ (clientUI ↔ server_multiMove)** — dispatched by `elen` (message length)

| `elen` | Mode | Data format | Description |
|--------|------|-------------|-------------|
| 3 | State motion | `(path, sequence, head_or_tail)` | Pre-defined path execution (existing) |
| 6 | Joint streaming | `(j1, j2, j3, j4, j5, j6)` | 6 axis values in degrees (new) |
| 3 | Termination | `(0, 0, 0)` | Shutdown command (existing) |

**Layer 2: TCP/IP (server_multiMove ↔ commModule)** — dispatched by header character

| Header | Format | Description |
|--------|--------|-------------|
| `d` | `d;path;tool;speed;state;` | Standard pre-defined state motion (existing) |
| `j` | `j;j1;j2;j3;j4;j5;j6;` | Joint streaming - 6 axis values in degrees (new) |
| `I` | `I;...` | Connection handshake (existing) |
| `T` | `T;...` | Termination (existing) |

**Translation**: server_multiMove bridges the two layers:
- `elen == 3` → `send_data(data_list, 'd;')` → RAPID receives `d;...`
- `elen == 6` → `send_data(joint_values, 'j;')` → RAPID receives `j;...`

---

## Files Modified

**1. commModule.mod** (`/ABB RAPID/commModule.mod`)
- Extended `dataPacket` RECORD with 6 joint streaming fields (`streamJ1`-`streamJ6`)
- Added PERS variables:
  - `operationMode` ("d" or "j") - mode toggle shared across tasks
  - `streamJointTarget_R1` - jointtarget for R1 streaming
  - `newStreamTarget_R1` - flag to trigger R1 joint motion
- Updated `ParseMessage` to parse "j" header with 6 semicolon-delimited joint values
- Updated `updateGlobalVariable` "j" case to populate `streamJointTarget_R1` and set `newStreamTarget_R1`
- Modified `cmdExe` dispatch: "j" mode sets `executionNotCompleted_R1` only (R2 not involved in first draft)

**2. MainModule_ROB1.mod** (`/ABB RAPID/MainModule_ROB1.mod`)
- Added PERS declarations: `operationMode`, `streamJointTarget_R1`, `newStreamTarget_R1`
- Updated `KeepLooping` to check `newStreamTarget_R1` flag (independent of `newTargetFlag_R1`)
- Added `Run_Joint_Stream_R1` procedure:
  - Executes `MoveAbsJ streamJointTarget_R1, v1000, z5, tool0`
  - Protected by same Global Eject ERROR handler as standard motion
  - Handles `ERR_INTERRUPT` for DI signal compatibility with PHASE 1

**3. MainModule_ROB2.mod** (`/ABB RAPID/MainModule_ROB2.mod`)
- Added `PERS string operationMode` declaration for cross-task PERS compatibility
- No motion changes for R2 in this first draft

**4. server_multiMove.py** (`/PythonHMI/server_multiMove.py`)
- Added `send_joint_stream()` function: sends `j;` prefixed joint values to RAPID, waits for ACK_DONE
- Added `run_streaming_test()` function: 20-point sine wave test on J1 — standalone utility for direct testing (bypasses ZMQ/clientUI, communicates directly with RAPID via TCP/IP)
- **Revised (2026-02-10)**: Mode dispatch uses `elen` (message length), NOT `data[0]`:
  - `elen == 3`: state motion `(path, sequence, head_or_tail)` — existing format preserved
  - `elen == 6`: joint streaming `(j1, j2, j3, j4, j5, j6)` — no conflict with path numbers
- **Bug fix**: Buffer size check used `struct.calcsize(fmt_elen)` (always 4) instead of `struct.calcsize(fmt_data)` (actual data size). Fixed in both startup and main loop checks.

**5. clientUI.py** (`/PythonHMI/clientUI.py`)
- **Added (2026-02-10)**: Streaming mode via 's' option in user input prompt
- User input flow: `'y'` = state motion (existing), `'s'` = streaming mode (new), `'n'` = quit (existing)
- Streaming sub-menu:
  - Manual: enter 6 comma-separated joint values (e.g., `0,0,0,0,0,0`)
  - Test: type `test` for 20-point sine wave on J1 (+/- 5 deg)
  - Exit: type `q` to return to main menu
- Packs joint values as `elen == 6` (6 doubles) for server_multiMove dispatch

---

## Architecture Decisions
- **ROB1 only** for this first draft - R2 streaming will follow after validation
- **Single-point execution** (not circular buffer yet) - establishes protocol before optimizing throughput
- **Unified ACK** maintained - commModule sends ACK_DONE after joint motion completes, same as standard mode
- **PHASE 1 compatibility** - interrupt TRAP handlers work during joint streaming motion
- **Decoupled architecture preserved** - commModule handles parsing/routing, MainModule_ROB1 handles motion

---

## Clean ZMQ Shutdown (2026-02-10)

Both `server_multiMove.py` and `server_cobot.py` now support graceful Ctrl+C shutdown:

**Implementation:**
- `zmq.RCVTIMEO = 5000` on receive sockets — `recv()` returns every 5s so Ctrl+C can interrupt
- `zmq.Again` exception handling — retries on timeout instead of crashing
- `KeyboardInterrupt` handler — breaks out of main loop cleanly
- Unified cleanup path at end of `main()` — closes all sockets regardless of exit reason (normal termination command from clientUI OR Ctrl+C)

**Cleanup sequence:**
1. Send `T;` termination to ExtSocketServer (RAPID) and close TCP/IP socket
2. Close ZMQ receive and send sockets
3. `context.term()` to release ZMQ context

**Error handling in cleanup:** The ExtSocketServer cleanup is wrapped in `try/except Exception: pass` because the RAPID controller (ExtSocketServer) typically breaks first in error scenarios — by the time Python needs to clean up, the TCP/IP socket is already dead. This is expected behavior, not a limitation.

**Operational note:** In practice, the handshake always breaks from the RAPID/ExtSocketServer side first (robot controller error, manual stop, etc.), leaving the Python servers idling. Ctrl+C then cleanly shuts down the ZMQ layer without needing to worry about the already-dead TCP/IP connection.

---

## Testing Checklist
- [ ] Load modified RAPID modules into robot controller
- [ ] **Test 1 - Standard Regression**: clientUI → 'y' → path selection → verify existing state motion works
- [ ] **Test 2 - Joint Stream (manual)**: clientUI → 's' → enter `0,0,0,0,0,0` → verify R1 moves to position
- [ ] **Test 3 - Joint Stream (test)**: clientUI → 's' → type `test` → verify 20-point sine wave on J1
- [ ] **Test 4 - Mode Switch**: Run state motion ('y'), then streaming ('s'), then state motion again
- [ ] **Test 5 - Interrupt During Stream**: Trigger DI during joint stream motion, verify PHASE 1 works

---

## Next Iteration
After validation, implement the circular buffer ("Leaky Bucket") for continuous streaming without per-point ACK wait.

---

## Reference: Gemini Conversation (Leaky Bucket Architecture)

Since you do not have the EGM (Externally Guided Motion) option, you are entering the realm of "standard socket streaming." This is challenging because the RAPID interpreter is not designed for real-time 30 Hz updates like a joystick. If the robot finishes a move before the next one arrives and is processed, it must stop (stutter). If you buffer too many points, the robot moves smoothly but the camera feedback is old (latency).

Here is the architectural blueprint to achieve ~30 Hz (or close to it) visual servoing without EGM using a Producer-Consumer model.

### 1. The Architecture: "The Leaky Bucket"

You need to decouple the communication (receiving data) from the motion (executing moves). You mentioned you already have a background communication script—this is your "Producer." Your main motion loop is the "Consumer."

- **Global Variable (The Bucket)**: A shared array (or circular buffer) of robtargets between the background and main task.
- **Producer (Background)**: Reads from the socket as fast as possible. If a new packet arrives, it puts it into the buffer.
- **Consumer (Motion)**: Peeks at the buffer. If there are points available, it executes a MoveL with a Zone (blending radius).

### 2. Synchronization: The "Pre-fetch" Strategy

You cannot strictly "clock" the robot to 30 Hz. Instead, you synchronize by managing the Buffer Level.

- **ROS 2 (Sender)**: Sends pose updates at a fixed rate (e.g., 30 Hz).
- **RAPID (Receiver)**:
  - **Startup**: Wait until the buffer has N points (e.g., 5 points) before starting the first move. This is your "safety margin" against stuttering.
  - **Running**: The robot executes MoveL. Because you use a blending zone (e.g., z1 or z5), the robot's "Lookahead" feature will peek at the next instruction while executing the current one.

### 3. The Trade-off: Latency vs. Stuttering

This trade-off is controlled entirely by two variables: Buffer Length and Zone Size.
- **Low Latency**: buffer size 1-2 points, Zone z0/fine → High Stutter Risk. Robot moves to point A, stops, asks "what's next?", then moves to B. Movement is jerky.
- **Smooth Motion**: buffer size 10+ points, Zone z10/z50 → High Latency. The robot is executing a point received 300ms ago. Visual servoing will oscillate or overshoot.
- **The Sweet Spot**: buffer size 3-5 points, Zone z1-z5 → Robot blends corners smoothly. Latency is manageable (~100-150ms).

### 4. Implementation Steps

#### A. The Shared, Global Data (Global Module)

Create a PERS (Persistent) global array accessible by both tasks.

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

#### B. The Background Task (Producer/Receiver)

This task does nothing but shovel data from the socket to the array. It looks at the incoming data header to decide if it's a "Standard Package" or a "Stream Point."

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

#### C. The Main Motion Task (Consumer/Motion Executer)

You use MoveL with a zone to prevent stopping. This task waits for the buffer to fill slightly, then moves.

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

#### D. Python GUI Implementation (The Simulator)

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

### 5. Critical Tips for 30 Hz Success

- **Filter Small Moves**: In your ROS 2 node, before sending a point, check the distance from the previous point. If the robot moves only 0.1mm, do not send it. The RAPID interpreter takes time to process every instruction (approx 3-10ms). If you flood it with microscopic moves, the interpreter will lag behind reality.
- **ROS 2 Rate Limiting**: Ensure your ROS 2 node publishes at a strict rate. If it bursts (sends 10 points in 1ms), your buffer fills up instantly, increasing latency.
- **Use \Conc?** You might see advice to use the \Conc (Concurrent) switch in MoveL. For this specific buffer setup, it is usually not necessary because the Zone (z5) already handles the lookahead.
- **Tuning Latency**: Start with a buffer "start threshold" of 5 points. Slowly decrease it (4, 3, 2) until you see the robot physically jerk/stop. Then add 1 back. That is your minimum latency floor.

**Troubleshooting:**
- **Problem A: Robot Stutters** — Buffer hits 0, robot stops. Fix: Increase anti-starvation threshold (> 5) or increase zone size (z10/z20).
- **Problem B: Robot Lags** — Too many points buffered. Fix: Decrease anti-starvation threshold (> 2).

### Integration with PHASE 1 (The Interrupt)

The Interrupt Trap (PHASE 1) works perfectly here. If you trigger the DI signal while in Main_Motion loop:
1. The TRAP triggers
2. StopMove executes
3. The loop breaks
4. You can set is_streaming := FALSE in your error handler to force the system back to a safe state
