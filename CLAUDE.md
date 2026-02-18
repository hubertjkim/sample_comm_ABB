# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
**Always check `ACTIVE_PHASE` in CLAUDE.md before making changes.**
**Always update the relevant PHASE markdown file before making changes.**
**Always ask permission to modify any script**


**CURRENT STATUS**: PHASE 2 single-point streaming verified (2026-02-17). Leaky bucket iteration next.
**PHASE 1 STATUS**: VALIDATED (2026-02-10). ExitCycle approach works. SyncMoveOn replaced with WaitSyncTask + independent moves.
**NEXT STEP**: Implement circular buffer (Leaky Bucket) for continuous streaming

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

***Please make sure not to move ahead, unless the current stage is fully completed.***

### PHASE 1 (VALIDATED): Interrupt-driven feedback for the ROBOT
- **Details**: [PHASE_1.md](PHASE_1.md)
- **Goal**: Implement the digital input interrupt inside the nested loop of RAPID script.
- **Status**: ✅ Validated 2026-02-10. ExitCycle approach with WaitSyncTask (replacing SyncMoveOn) confirmed working in RobotStudio.

### PHASE 2 (ACTIVE_PHASE): Enable Streaming feature (Python + RAPID)
- **Details**: [PHASE_2.md](PHASE_2.md)
- **Goal**: Use the "Leaky Bucket" architecture for data streaming between Python and ABB RAPID code.
- **Status**: ⏳ Single-point verified (2026-02-17). Circular buffer (Leaky Bucket) plan outlined, implementation next.

### PHASE 3 (Future_PHASE): Enable ROS2 via Docker/WSL2
- **Details**: [PHASE_3.md](PHASE_3.md)
- **Goal**: Finalize the handshake platform between ROS2 and RobotStudio.
- **Status**: Not started.

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
