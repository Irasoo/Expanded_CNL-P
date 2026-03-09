"""
xx01x: 多个MAIN_FLOW
xx02x: 空的BLOCK
xx03x: BLOCK的嵌套问题
xx04x: 空的SECTION
"""

task03_json_format = {
    "task_description": "The usage of these CNL-P identifiers is not problematic, but there are still some non-standard issues in the overall structure.",
    "instances": [
        {
            "id": 31011,
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
        
        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "Can you describe your current mood, energy level, and any physical discomfort?" VALUE user_condition: ConsultationState SET]
                COMMAND-2 [COMMAND Combine <REF> user_condition </REF> with <REF> health_info </REF> and <REF> diet_preference </REF> to create initial dietary_recommendation: text SET]
                COMMAND-3 [DISPLAY Present the personalized <REF> dietary_recommendation </REF> with key rationale]
                COMMAND-4 [INPUT Ask user 'Would you like to modify anything in this recommendation?' VALUE user_wants_change: boolean SET]
            [END_SEQUENTIAL_BLOCK]

            [WHILE User wants change]
                COMMAND-5 [INPUT DISPLAY Ask "Please specify what you'd like to modify or what's not suitable." VALUE user_change_request: text SET]
                COMMAND-6 [COMMAND Revise <REF> dietary_recommendation </REF> based on <REF> user_change_request </REF> RESULT dietary_recommendation: text SET]
                COMMAND-7 [INPUT DISPLAY Do you need further changes? VALUE <REF> user_wants_change </REF> SET]
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
                "start_line": 89,
                "end_line": 89,
                "error_content": "",
                "error_message": "There can only be and must be one MAIN_FLOW in the worker, but in fact this is the 2nd MIAN_FLOW.",
            },
        },
        {
            "id": 31021,
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
            [END_SEQUENTIAL_BLOCK]  
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 113,
                "end_line": 114,
                "error_content": "",
                "error_message": "This is an empty block without command",
            }
        },
        {
            "id": 31031,
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
                [SEQUENTIAL_BLOCK]
                    COMMAND-10 [COMMAND According to <REF> health_info </REF>, <REF> diet_preference </REF>, <REF> avoidance_rules </REF> and <REF> user_state </REF>, generate the dietary recommendation RESULT dietary_recommendation: text SET]
                [END_SEQUENTIAL_BLOCK] 
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
                "start_line": 90,
                "end_line": 97,
                "error_content": "",
                "error_message": "Newly defined BLOCK was nested within the previous BLOCK.",
            }
        },
        {
            "id": 32011,
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

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT Ask user: "What type of scenery, climate, and activity are you currently in the mood for?" VALUE user_trip_mood: TravelIntent SET]
                COMMAND-2 [COMMAND Match <REF> user_trip_mood </REF> with <REF> destination_preference </REF> and <REF> travel_profile </REF> to produce candidate_locations: List[text] SET]
                COMMAND-3 [DISPLAY These destinations fit your vibe right now: <REF> candidate_locations </REF>]
                COMMAND-4 [INPUT DISPLAY Which of these catches your interest most? VALUE selected_destination: text SET]
                COMMAND-5 [COMMAND Create a personalized travel plan at <REF> selected_destination </REF> using <REF> user_trip_mood </REF> and <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-6 [DISPLAY Your customized travel itinerary: <REF> itinerary </REF>]
                COMMAND-7 [INPUT DISPLAY Does this itinerary excite you? VALUE suggestion_feedback: SuggestionFeedback SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF> suggestion_feedback.satisfied </REF> == false]
                COMMAND-8 [COMMAND Refine itinerary based on <REF> suggestion_feedback.comment </REF> and <REF> travel_profile </REF> RESULT itinerary: Itinerary SET]
                COMMAND-9 [DISPLAY Here’s the updated travel suggestion: <REF> itinerary </REF>]
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
                "start_line": 106,
                "end_line": 106,
                "error_content": "",
                "error_message": "There can only be and must be one MAIN_FLOW in the worker, but in fact this is the 2nd MIAN_FLOW.",
            }
        },
        {
            "id": 32021,
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
            [END_SEQUENTIAL_BLOCK]
        [END_ALTERNATIVE_FLOW]

        [EXCEPTION_FLOW: Incompatible destination input]
            LOG User selected a destination that violates constraints
            [SEQUENTIAL_BLOCK]
                COMMAND-13 [DISPLAY The destination you chose may be unsafe or restricted. Please pick another.]
            [END_SEQUENTIAL_BLOCK]
        [END_EXCEPTION_FLOW]
    [END_WORKER]
[END_AGENT]
""",
            "sample_answer": {
                "start_line": 116,
                "end_line": 117,
                "error_content": "",
                "error_message": "This is an empty block without command.",
            },
        },
        {
            "id": 32031,
            "cnl_p":"""
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
                [SEQUENTIAL_BLOCK]
                    COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                    COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
                [END_SEQUENTIAL_BLOCK]
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
                "start_line": 100,
                "end_line": 105,
                "error_content": "",
                "error_message": "Newly defined BLOCK was nested within the previous BLOCK.",
            }
        },
        {
            "id": 32032,
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
                [IF <REF> suggestion_feedback.satisfied </REF> == false]
                    COMMAND-7 [COMMAND Modify itinerary using <REF> suggestion_feedback.comment </REF> and <REF> selected_destination </REF> RESULT itinerary: Itinerary SET]
                    COMMAND-8 [DISPLAY Updated itinerary: <REF> itinerary </REF>]
                [END_IF]
            [END_SEQUENTIAL_BLOCK]
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
                "start_line": 91,
                "end_line": 102,
                "error_content": "",
                "error_message": "The previous BLOCK definition was not properly closed, or the newly defined BLOCK was nested within the previous BLOCK.",
            }
        }
    ],
}