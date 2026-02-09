MODULE commModule

    ! ====================================================
    ! COMMUNICATION MODULE - Socket Interface
    ! ====================================================
    ! PHASE 1: Enhanced with interrupt-driven feedback
    ! - Monitors wasInterrupted flags from MainModules
    ! - Waits for BOTH ROB1 and ROB2 to complete before acknowledgment
    ! - Sends unified acknowledgment regardless of interrupt status
    ! ====================================================

    ! data structure to store the incoming data
    RECORD dataPacket
        string commHeader;
        robtarget tmpTarget;
        jointtarget tmpJoint;
        num selectedPath;
        num selectedTool;
        num selectedSpeed;
        num selectedState;
    ENDRECORD 

    CONST num R1_PortNo := 5024;
    CONST string R1_IPAddress := "127.0.0.1";

    VAR socketdev serverSocket;
    VAR socketdev clientSocket;
    VAR string clientIP;
    VAR dataPacket receivedDataPkg;
    VAR string mydata;

    PERS bool initialRun;

    !shared variable accross tasks
    PERS string smIndx;
    PERS bool reconnectComm;
    PERS bool executionNotCompleted_R1;
    PERS bool executionNotCompleted_R2;
    PERS bool newTargetFlag_R1;
    PERS bool newTargetFlag_R2;

    ! PHASE 1: Interrupt status flags (shared with MainModules)
    PERS bool wasInterrupted_R1;
    PERS bool wasInterrupted_R2;

    PERS num pathChoice;
    PERS num toolChoice;
    PERS num speedChoice;
    PERS num stateChoice;
    PERS num stateChoice_prev;

    PROC commMain()
        TPErase;
        executionNotCompleted_R1 := FALSE;
        executionNotCompleted_R2 := FALSE;
        reconnectComm := FALSE;
        initialRun := TRUE;
        cmdExe;
    ENDPROC

    PROC cmdExe()
        IF reconnectComm = FALSE THEN
            ! create socket
            SocketCreate server_socket;
            SocketBind server_socket, R1_IPAddress, R1_PortNo;
            SocketListen server_socket;
            TPWrite "Waiting for client connection...";
            SocketAccept server_socket, client_socket\ClientAddress:=clientIP, \Time:=WAIT_MAX;
            TPWrite clientIP;
        ENDIF

        WHILE TRUE DO

            ! wait for the motion task to be completed
            WHILE executionNotCompleted_R1 OR executionNotCompleted_R2 DO
                WaitTime 0.1;
            ENDWHILE

            IF initialRun THEN
                initialRun := FALSE;
            ELSE
                ! ====================================================
                ! PHASE 1: UNIFIED ACKNOWLEDGMENT PROTOCOL
                ! ====================================================
                ! After BOTH ROB1 and ROB2 have completed (or been interrupted),
                ! send a single unified acknowledgment to the client.
                ! This maintains synchronization for the multimove system.
                ! ====================================================

                ! Log interrupt status for diagnostics
                IF wasInterrupted_R1 OR wasInterrupted_R2 THEN
                    TPWrite "*** Motion interrupted (R1: "\Bool:=wasInterrupted_R1\", R2: "\Bool:=wasInterrupted_R2")";
                ELSE
                    TPWrite "Motion completed successfully for both robots";
                ENDIF

                ! Send unified acknowledgment (same message regardless of interrupt)
                TPWrite "Sending acknowledgment to client";
                SocketSend client_socket\str:='ACK_DONE';

                ! Reset interrupt flags for next cycle
                wasInterrupted_R1 := FALSE;
                wasInterrupted_R2 := FALSE;

                stateChoice_prev := stateChoice; ! store the previous state choice for comparison
            ENDIF

            ! Wait for data from the client
            SocketReceive client_socket\str:mydata\Time:=WAIT_MAX;

            ! If receipt, trigger:
            IF NOT mydata = "" THEN
                ! Show incoming data
                TPWrite mydata;
                ! assign the incoming data to the data structure
                receivedDataPkg := ParseMessage (mydata)
                updateGlobalVariable(receivedDataPkg)

                IF NOT stateChoice_prev = stateChoice THEN
                    ! Make the motion task execute the new target
                    newTargetFlag_R1 := TRUE;
                    newTargetFlag_R2 := TRUE; ! trigger the motion task to execute the new target
                    executionNotCompleted_R1 := TRUE; ! set the execution flag to true
                    executionNotCompleted_R2 := TRUE; ! set the execution flag to true
                ELSE
                    TPWrite "Same state choice as before, not executing motion";
                    initialRun := TRUE; ! reset the initial run flag to avoid skipping the next execution
                    SocketSend client_socket\str:='ACK_DONE'; ! send unified acknowledgment (no motion executed)
                ENDIF

                TPWrite "Waiting for next client data...";
            ENDIF
        ENDWHILE

    ERROR
    IF ERRNO = ERR_SOCKET_TIMEOUT THEN
        TPWrite "Socket timeout, no data received.";
        TPWrite ERRNO;
        RETRY;
    ELSEIF ERRNO = ERR_SOCK_CLOSED THEN
        TPWrite "Handling error for closed socket";
        TPWrite ERRNO;
    ELSE
        TPWrite "An error occurred: "\Num:=ERRNO
    ENDIF;

    ENDPROC

    PROC updateGlobalVariable (dataPkg receivedDataPkg)
    
        smIndx := receivedDataPkg.commHeader;
        
        TEST smIndx
        CASE "j": ! update absolute position of the robot
            !placeholder for streamingg the absolute position data
        CASE "d": ! update the data structure with the incoming data
            pathChoice := receivedDataPkg.selectedPath;
            toolChoice := receivedDataPkg.selectedTool;
            speedChoice := receivedDataPkg.selectedSpeed;
            stateChoice := receivedDataPkg.selectedState;
        CASE "I":
            TPWrite "TCP/IP connection established with client at IP";
            SocketSend client_socket\str:='1,1,1,1,1,1'; ! send a signal to the client that the connection is established
        CASE "T":
            TPWrite "TCP/IP connection closed";
            reconnectComm := TRUE; ! set the reconnect flag to true to trigger reconnection in the main loop
            SocketClose client_socket; ! close the client socket
            SocketClose server_socket; ! close the server socket
        ENDTEST
    ENDPROC

    FUNC dataPacket ParseMessage (string message)
        VAR num pkgHeader;
        VAR bool bResult;
        VAR num data_1;
        VAR num data_2;
        VAR num data_3;
        VAR num data_4;
        VAR num data_5; 
        VAR num data_6; 

        VAR dataPacket packet_receive;
        pkgHeader := StrFind(message, 1, ";"); ! find the position of the first comma to extract the header
        packet_receive.commHeader := StrPart(message, 1, pkgHeader - 1);

        IF packet_receive.commHeader = "d" THEN
            ! if the header is "d", extract the data values
            data_1 := StrFind(message, pkgHeader + 1, ";"); ! find the position of the second comma to extract data 1
            data_2 := StrFind(message, data_1 + 1, ";"); ! find the position of the third comma to extract data 2
            data_3 := StrFind(message, data_2 + 1, ";"); ! find the position of the fourth comma to extract data 3
            data_4 := StrFind(message, data_3 + 1, ";"); ! find the position of the fifth comma to extract data 4
            bResult := StrToVal(StrPart(message, pkgHeader + 1, data_1 - pkgHeader - 1), packet_receive.selectedPath);
            bResult := StrToVal(StrPart(message, data_1 + 1, data_2 - data_1 - 1), packet_receive.selectedTool);
            bResult := StrToVal(StrPart(message, data_2 + 1, data_3 - data_2 - 1), packet_receive.selectedSpeed);
            bResult := StrToVal(StrPart(message, data_3 + 1, data_4 - data_3 - 1), packet_receive.selectedState);

        ENDIF
    RETURN packet_receive

ENDMODULE