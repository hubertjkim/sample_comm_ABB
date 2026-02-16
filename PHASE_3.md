# PHASE 3: ROS2 Integration (Future)

**Status**: Future — not started
**Goal**: Finalize the handshake platform between ROS2 and RobotStudio.
**Restriction**: Environment can't support dual boot. Always Docker with WSL2 is the only option.

---

## Plan

- Switch the current Python interface to ROS2 running in a Docker container via WSL2
- All previous features (state motion, joint streaming, interrupt) remain the same
- During streaming mode, ROS2 controls the robot motion with external cameras, providing the 6 DOFs to RAPID
- Apply the "Leaky Bucket" circular buffer algorithm from PHASE 2 into ROS2 nodes
