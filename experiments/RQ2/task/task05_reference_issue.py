task05_json_format = {
    "task_description": "This task describes the incorrect citation of CNL-P.",
    "instances": [
        {
            "id": 51011,
            "cnl_p": """
[DEFINE_AGENT: DietAdvisor "An AI agent that gives users dietary advice based on their health information and real-time interaction."]

    [DEFINE_PERSONA:]
        ROLE: I hope you can become an AI assistant and the task is <REF> task_goal <REF>
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
                COMMAND-18 [DISPLAY Missing fields detected: <REF> missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 4,
                "end_line": 4,
                "error_content": "ROLE: I hope you can become an AI assistant and the task is <REF> task_goal <REF>",
                "error_message": "The '<REF>' and '</REF>' identifiers have pairing errors.",
            },
        },
        {
            "id": 51012,
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
                COMMAND-2 [COMMAND According to <REF> health_info, diet_preference, user_state </REF>, generate the dietary_recommendation: text SET]
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
                "error_content": 'COMMAND-2 [COMMAND According to <REF> health_info, diet_preference, user_state </REF>, generate the dietary_recommendation: text SET]',
                "error_message": "The content '<REF> health_info, diet_preference, user_state </REF>' has an error: Too many parts inside <REF>... only asterisk and one variable allowed",
            }
        },
        {
            "id": 51013,
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

        [ALTERNATIVE_FLOW: <REF> User's BMI <REF> is extreme (e.g., > 40)]
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
                "start_line": 98,
                "end_line": 98,
                "error_content": "<REF> User's BMI <REF> is extreme (e.g., > 40)",
                "error_message": "The '<REF>' and '</REF>' identifiers have pairing errors.",
            }
        },
        {
            "id": 51014,
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
                COMMAND-18 [DISPLAY Missing fields detected: missing_keys </REF>. Please fill them and restart.]
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 115,
                "end_line": 115,
                "error_content": 'COMMAND-18 [DISPLAY Missing fields detected: missing_keys </REF>. Please fill them and restart.]',
                "error_message": "The '<REF>' and '</REF>' identifiers have pairing errors.",
            }
        },
    ]
}