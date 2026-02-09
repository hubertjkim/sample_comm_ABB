MODULE

    PROC main()
        TPErase;
        TPWrite "Main module started.";
        
        assignWaypoints;

        ConfJ \Off;
        state_HOME;
        ConfJ \On;

        KeepLooping;
    ENDPROC

    PROC KeepLooping()
        WHILE TRUE DO
            IF newTargetFlag_R1 = TRUE THEN
                newTargetFlag_R1 := FALSE;
                IF smIndx = "d" THEN
                    TEST pathChoice
                    CASE 1:
                        TPWrite "Executing path 1";
                        executeState pathChoice, stateChoice, absPoints_obj1_R1;
                    CASE 2:
                        TPWrite "Executing path 2";
                        executeState pathChoice, stateChoice, absPoints_obj2_R1;
                    DEFAULT:
                        TPWrite "Invalid path choice.";
                    ENDTEST

                    WaitSyncTask syncEND, all_tasks;

                ELSEIF smIndx = "I" THEN
                    TPWrite "R1, ACK to client";
                ELSEIF smIndx = "T" THEN
                    TPWrite "R1, comm closed by client";
                ELSE
                    TPWrite "Invalid robot index." + smIndx;
                ENDIF
                
                executionNotCompleted_R1 := FALSE; ! reset the execution flag to indicate completion
                TPWrite "R1, execution completed, waiting for next command.";
            ENDIF
            WaitTime 0.25; ! wait for a short time before checking the flag again
        ENDWHILE
    ENDPROC

    PROC executeState (num pathChoice, num stateChoice, absPointStruct tempPointStruct)
        VAR string stateChoiceString;
        VAR tooldata toolTemp;
        VAR wobjdata tempWobj;

        ! Adjust the TCP based on the modification
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

ENDMODULE