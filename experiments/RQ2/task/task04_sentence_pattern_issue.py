"""
xx01x: optional_aspect issue
xx02x: general_command issue
xx03x: input_command issue
xx04x: call_command issue
xx05x: display_command issue
xx06x: examples issue
"""
from ctypes.wintypes import PWORD

task04_json_format = {
    "task_description": "The examples described in this task all involve the use of identifiers and have no problems in the macro structure, but there are grammatical errors within the sentences. These are CNL-P instances.",
    "instances": [
        {
            "id": 41011,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        communicationatyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 5,
                "end_line": 5,
                "error_content": "communicationatyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.",
                "error_message": "The optional aspect name is a capitalized word.",
            }
        },
        {
            "id": 41021,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT IN dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 77,
                "end_line": 77,
                "error_content": "COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT IN dietary_recommendation: text SET]",
                "error_message": "The use of 'RESULT IN' does not conform to the general command pattern.",
            }
        },
        {
            "id": 41031,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' and put the value in variable user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 79,
                "end_line": 79,
                "error_content": "COMMAND-4 [INPUT Ask user 'are you satisfied now?' and put the value in variable user_satisfied: boolean SET]",
                "error_message": "INPUT COMMAND requires keyword: 'VALUE'.",
            }
        },
        {
            "id": 41041,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL 1st_disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 91,
                "end_line": 91,
                "error_content": "COMMAND-8 [CALL 1st_disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]",
                "error_message": "Invalid function name: 1st_disease_avoidance_check",
            }
        },
        {
            "id": 41042,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITHIN {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 91,
                "end_line": 91,
                "error_content": "COMMAND-8 [CALL 1st_disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]",
                "error_message": "CALL COMMAND requires keyword: 'WITH', not 'WITHIN'",
            },
        },
        {
            "id": 41051,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAYS Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 115,
                "end_line": 115,
                "error_content": "COMMAND-18 [DISPLAYS Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]",
                "error_message": "There is no 'DISPLAYS' type of COMMAND.",
            }
        },
        {
            "id": 41061,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8 medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 61,
                "end_line": 71,
                "error_content": """ {health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8 medical_history: "None", current_conditions: "Healthy" },diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }}'""",
                "error_message": "Invalid input structure",
            }
        },
        {
            "id": 41062,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst: Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: [COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7]
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 0,
                "end_line": 0,
                "error_content": "execution-path: [COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7]",
                "error_message": "Dose not match the pattern of 'execution-path.",
            }
        },
        {
            "id": 42011,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal </REF>
        CommunicationStyle: You should respond in a professional yet empathetic tone when giving users suggestions about diet.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        TargetUserType: You will interact with users who provide varying degrees of health information, including people with medical histories.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        SafetyFirst Always prioritize food safety when recommending any dietary advice.
        RespectPreference: Always balance user preferences while keeping nutritional principles in mind.
        BMICategory: For adults, BMI < 18.5 is underweight, and BMI > 30 is obese.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        FoodSafety: Do not recommend foods that require special preparation like pufferfish or certain fungi.
        ExtremeBehavior: Do not suggest overeating, starvation, or unsafe dietary practices.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        "User health and diet profile"
        HealthInfo = {
            " REQUIRED" height_cm: number,
            " REQUIRED" weight_kg: number,
            " REQUIRED" BMI: number,
            " REQUIRED" medical_history: text,
            " REQUIRED" current_conditions: text
        }

        DietPreference = {
            " REQUIRED" favorite_foods: text,
            " REQUIRED" disliked_foods: text,
            " REQUIRED" like_sweet: boolean,
            " REQUIRED" like_spicy: boolean,
            " REQUIRED" accept_sour: boolean,
            " REQUIRED" like_heavy_flavor: boolean
        }

        ConsultationState = {
            " REQUIRED" mood: text,
            " REQUIRED" recent_activity: text,
            " REQUIRED" appetite: text,
            " REQUIRED" craving: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Main workflow that collects user state and provides suggestions" MainInteraction]
        [INPUTS] 
            REQUIRED <REF> health_info </REF>
            REQUIRED <REF> diet_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> dietary_recommendation </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    health_info: { height_cm: 170, weight_kg: 60, BMI: 20.8, medical_history: "None", current_conditions: "Healthy" }, 
                    diet_preference: { favorite_foods: "rice, chicken", disliked_foods: "mushrooms", like_sweet: true, like_spicy: false, accept_sour: true, like_heavy_flavor: false }
                },
                expected-outputs: {
                    dietary_recommendation: "Based on your current health and preferences, we suggest a warm chicken soup with rice, avoiding mushrooms. Let us know if you'd like changes.", 
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6, COMMAND-7
            } </EXPECTED-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-2 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF> and <REF> user_state </REF>, generate the dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Show the user the <REF> dietary_recommendation </REF>]
                COMMAND-4 [INPUT Ask user 'are you satisfied now?' VALUE user_satisfied: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User not satisfied]
                COMMAND-5 [INPUT DISPLAY Ask why you're not satisfied VALUE user_feedback: text SET]
                COMMAND-6 [COMMAND Improve suggestion based on <REF> user_feedback </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Are you satisfied now? VALUE <REF> user_satisfied </REF> SET]
            [END_WHILE]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User has major health condition]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL disease_avoidance_check WITH {medical_history: <REF> health_info.medical_history </REF>, current_conditions: <REF> health_info.current_conditions </REF>} RESPONSE avoidance_rules: text SET]
                COMMAND-9 [INPUT Ask user: "How do you feel right now, what have you done recently, and what would you like to eat?" VALUE user_state: ConsultationState SET]
                COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                COMMAND-11 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and it was repeatedly emphasized that the actual diet plan should be formulated by a professional doctor.]
            [END_SEQUENTIAL_BLOCK]   
        [END_ALTERNATIVE_FLOW]

        [ALTERNATIVE_FLOW: User's BMI is extreme (e.g., > 40)]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Ask user: "Your BMI appears unusually high. Is this correct?" VALUE user_confirmed: boolean SET]
            [END_SEQUENTIAL_BLOCK]   
            [IF <REF> user_confirmed </REF> == false]
                COMMAND-13 [DISPLAY Please correct your input data in the system. Agent will now exit.]
            [ELSE]
                COMMAND-14 [COMMAND Reassess <REF> health_info </REF> and <REF> diet_preference </REF> under the context of extreme obesity RESULT refined_profile: text SET]
                COMMAND-15 [COMMAND Generate a highly cautious dietary plan tailored for BMI > 40 RESULT dietary_recommendation: text SET]
                COMMAND-16 [DISPLAY Show the user the <REF> dietary_recommendation </REF>, and kindly suggest consulting a registered dietitian or physician for personalized guidance.]
            [END_IF]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Missing user health data]
            LOG Detected missing required health fields
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [COMMAND Check for missing keys in <REF> health_info </REF> and <REF> diet_preference </REF> RESULT missing_keys: text SET]
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 13,
                "end_line": 13,
                "error_content": "SafetyFirst Always prioritize food safety when recommending any dietary advice.",
                "error_message": "There should be a ':' between optional_aspect_name and description_with_reference",
            }
        },
        {
            "id": 42031,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 108,
                "end_line": 108,
                "error_content": "COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus SET]",
                "error_message": "Missing ':' in variable declaration",
            }
        },
        {
            "id": 42021,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT <REF> itinerary </REF> RESET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 101,
                "end_line": 101,
                "error_content": "COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT <REF> itinerary </REF> RESET]",
                "error_message": "COMMAND sentence does not have operation 'RESET'.",
            },
        },
        {
            "id": 42041,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-a [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-1 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-2 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-3 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-4 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-5 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-6 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-7 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-9 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-10 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-11 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-12 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-13 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-14 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-15 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-16 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 92,
                "end_line": 92,
                "error_content": "COMMAND-a [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]",
                "error_message": "COMMAND-<number> should be a number",
            }
        },
        {
            "id": 42051,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH max_budget: <REF> declared_budget </REF> RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]""",
            "sample_answer": {
                "start_line": 118,
                "end_line": 118,
                "error_content": "COMMAND-14 [CALL generate_budget_plan WITH max_budget: <REF> declared_budget </REF> RESPONSE optimized_plan: text SET]",
                "error_message": "In CALL command, The parameter object following “WITH” must be valid argument list: {...}",
            }
        },
        {
            "id": 42052,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference, <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 109,
                "end_line": 109,
                "error_content": "COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference, <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]",
                "error_message": "Each parameter must have a ':' separating formal parameter name and actual formal value.",
            }
        },
        {
            "id": 42061,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    ,
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
                defect-explanation: Output conflicts with user’s stated preference to avoid cold and mountains
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 62,
                "end_line": 87,
                "error_content": "",
                "error_message": "Invalid output structure",
            }
        },
        {
            "id": 42062,
            "cnl_p": """
[DEFINE_AGENT: TravelPlanner "An AI agent that helps users plan enjoyable and safe trips."]
    
    [DEFINE_PERSONA:]
        ROLE: You are a virtual travel planner that assists users in choosing destinations, planning itineraries, and providing advice.
        EmpathyLevel: Use an encouraging and flexible tone to match different user moods.
    [END_PERSONA]

    [DEFINE_AUDIENCE:]
        UserTypes: Users may be experienced travelers or beginners, with various expectations for comfort, adventure, or relaxation.
    [END_AUDIENCE]

    [DEFINE_CONCEPTS:]
        Seasonality: Consider the seasonal suitability of each destination.
        BudgetAwareness: Ensure travel plans respect the user's budget.
        LocalCaution: Highlight if destinations have known safety concerns.
    [END_CONCEPTS]

    [DEFINE_CONSTRAINTS:]
        SafetyFirst: Do not recommend destinations currently under severe travel advisories.
        NoOverload: Do not pack more than 3 major activities per day.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        TravelProfile = {
            "REQUIRED" traveler_name: text,
            "REQUIRED" budget_level: text,
            "REQUIRED" preferred_climate: text,
            "REQUIRED" adventure_level: number,
            "REQUIRED" prior_experience: text
        }

        DestinationPreference = {
            "REQUIRED" interest_tags: text,
            "REQUIRED" avoid_tags: text,
            "REQUIRED" travel_duration_days: number
        }

        SuggestionFeedback = {
            "REQUIRED" satisfied: boolean,
            "REQUIRED" comment: text
        }

        Itinerary = {
            "REQUIRED" destination: text,
            "REQUIRED" day_plan: text,
            "REQUIRED" warnings: text
        }
    [END_TYPES]

    [DEFINE_WORKER: "Assist user in selecting destination and producing plan" TravelFlow]
        
        [INPUTS]
            <REF> travel_profile </REF>
            <REF> destination_preference </REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF> itinerary </REF>
        [END_OUTPUTS]

        [EXAMPLES]
            <DEFECT-WORKER-BEHAVIOR> {
                Processing Logic Error,
                inputs: {
                    travel_profile: {
                        traveler_name: "Alice",
                        budget_level: "medium",
                        preferred_climate: "warm",
                        adventure_level: 6,
                        prior_experience: "some solo trips"
                    },
                    destination_preference: {
                        interest_tags: "beach, local food",
                        avoid_tags: "cold, mountain",
                        travel_duration_days: 5
                    }
                },
                defect-outputs: {
                    itinerary: {
                        destination: "Reykjavik",
                        day_plan: "Day 1: Ice cave tour. Day 2: Glacier hike. Day 3: Thermal spa. Day 4: Volcano hike. Day 5: Departure.",
                        warnings: "Cold weather expected; pack accordingly."
                    }
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-6,
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [COMMAND Filter potential destinations based on <REF> destination_preference </REF> and <REF> travel_profile </REF> RESULT shortlist: List[text] SET]
                COMMAND-2 [DISPLAY Based on your inputs, here are some destination options: <REF> shortlist </REF>]
                COMMAND-3 [INPUT DISPLAY Please choose your preferred destination VALUE selected_destination: text SET]
                COMMAND-4 [COMMAND Generate a suitable itinerary for <REF> selected_destination </REF> considering <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-5 [DISPLAY Here is your suggested plan: <REF> itinerary </REF>]
                COMMAND-6 [INPUT DISPLAY Are you happy with this plan? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]
        
            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
            [END_IF]
        [END_MAIN_FLOW]

        [ALTERNATIVE_FLOW: User prefers extreme adventure]
            [SEQUENTIAL_BLOCK]
                COMMAND-9 [INPUT DISPLAY What kind of extreme sports or thrill activities are you most interested in? VALUE adventure_focus: text SET]
                COMMAND-10 [CALL analyze_adventure_profile WITH {activity_preference: <REF> adventure_focus </REF>} RESPONSE risk_summary: text SET]
                COMMAND-11 [COMMAND Generate a suggestion plan for adventure travel using <REF> risk_summary </REF> RESULT adventure_plan: Itinerary SET]
                COMMAND-12 [DISPLAY Your plan includes high-adrenaline activities. Please ensure proper insurance and physical readiness before participating.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]
        
        [ALTERNATIVE_FLOW: User has low budget]
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [INPUT DISPLAY Please confirm your total available travel budget (in USD). VALUE declared_budget: number SET]
                COMMAND-14 [CALL generate_budget_plan WITH {max_budget: <REF> declared_budget </REF>} RESPONSE optimized_plan: text SET]
                COMMAND-15 [COMMAND Adjust recommendation list using <REF> optimized_plan </REF> RESULT budget_friendly_plan: Itinerary SET]
                COMMAND-16 [DISPLAY We've created a cost-effective itinerary. Actual costs may vary based on availability. Review carefully before booking.]
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-17 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 62,
                "end_line": 86,
                "error_content": "",
                "error_message": "Missing 'defect-explanation'.",
            }
        }
    ]
}