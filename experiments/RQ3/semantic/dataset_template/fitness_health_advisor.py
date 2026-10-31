spl_original = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

persona_referenced_global_variable_does_not_exist = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant. Your tasks are based on <REF>_fitness_goal</REF>.
        FUNCTION: Provide workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

constraint_referenced_global_variable_does_not_exist = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Avoid suggesting exercises that conflict with <REF>_fitness_restrictions</REF>.
    [END_CONSTRAINTS]


    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_undeclared_variable_reference_in_para = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
                COMMAND-15 [DISPLAY "Your workout summary: " <REF>workout_summary</REF>]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_duplicate_variable_declaration = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE _chosen_workout_type: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>_chosen_workout_type</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_variable_referenced_before_declaration = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>_workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_conditional_branch_scope_issue = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation_info: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

target_type_cannot_be_found = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: ExercisePlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

API_call_argument_type_mismatch = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>workout_plan</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

API_return_type_mismatch = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: text SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

non_existent_API = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [CALL fetch_fitness_data WITH {user: <REF>_user_account_fitness</REF>} RESPONSE fitness_data: dict SET]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

extraneous_API_parameters = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>, duration: 60} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

missing_API_parameters = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

unhandled_API_return_value = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [CALL submit_user_progress WITH {user: <REF>_user_account_fitness</REF>, plan: <REF>workout_plan</REF>}]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

unexpected_API_return_handling = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
                COMMAND-15 [CALL log_daily_activity WITH {user: <REF>_user_account_fitness</REF>, plan: <REF>workout_plan</REF>} RESPONSE _log_result: text SET]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

global_variable_naming_conflict = """   
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Workout and Diet Planning" FitnessRoutineWorkflow]
        [INPUTS]
            <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_user_account_fitness</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE workout_plan: WorkoutPlan SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _user_account_fitness: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _user_account_fitness: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _user_account_fitness: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_user_account_fitness</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

spl_indexes = {
    "Persona": {
        "Reference_Related_Errors": {
            "referenced_global_variable_does_not_exist": {
                "spl": persona_referenced_global_variable_does_not_exist,
                "error_path": "persona.ROLE.reference1",
                "error_reason": "The variable _fitness_goal referenced in <REF>_fitness_goal</REF> is not declared in the DEFINE_VARIABLES section or globally. This leads to an undefined reference."
            }
        }
    },
    "Constraints": {
        "Reference_Related_Errors": {
            "referenced_global_variable_does_not_exist": {
                "spl": constraint_referenced_global_variable_does_not_exist,
                "error_path": "constraints.FORBID.reference1",
                "error_reason": "The variable '_fitness_restrictions' is not declared in DEFINE_VARIABLES or as a global variable."
            }
        }
    },
    "Instruction": {
        "Scope_Related_Errors": {
            "undeclared_variable_reference": [
                {
                    "spl": instruction_undeclared_variable_reference_in_para,
                    "error_path": "instruction.main_flow.sequential_block3.command15",
                    "error_reason": "The variable 'workout_summary' referenced in <REF>workout_summary</REF> is not declared in DEFINE_VARIABLES or as a temporary variable."
                },
            ],
            "duplicate_variable_declaration": {
                "spl": instruction_duplicate_variable_declaration,
                "error_path": "instruction.main_flow.sequential_block1.command2",
                "error_reason": "The variable '_chosen_workout_type' was previously declared, so the current declaration will have no effect."
            },
            "variable_referenced_before_declaration": {
                "spl": instruction_variable_referenced_before_declaration,
                "error_path": "instruction.main_flow.sequential_block1.command6",
                "error_reason": "The variable '_workout_plan' is referenced before it has been assigned a value."
            }
        },
            "conditional_branch_scope_issue": {
                "spl": instruction_conditional_branch_scope_issue,
                "error_path": "instruction.main_flow.sequential_block3.command14",
                "error_reason": "The variable '_recommendation' may not have been assigned in the ELSE branch, leading to potential use of an uninitialized variable."
            }
        },
        "Type_Related_Errors": {
            "target_type_cannot_be_found": {
                "spl": target_type_cannot_be_found,
                "error_path": "instruction.main_flow.sequential_block1.command2",
                "error_reason": "The type 'ExercisePlan' used for the variable 'workout_plan' in COMMAND-2 is not declared in DEFINE_TYPES or globally."

            },
            "API_call_argument_type_mismatch": {
                "spl": API_call_argument_type_mismatch,
                "error_path": "instruction.main_flow.sequential_block1.command4",
                "error_reason": "The parameter 'preference' is passed as 'workout_plan' from workout_plan, but the API get_diet_plan expects 'WorkoutPlan' to be of type 'str'."
            },
            "API_return_type_mismatch": {
                "spl": API_return_type_mismatch,
                "error_path": "instruction.main_flow.sequential_block1.command2",
                "error_reason": "The API 'get_workout_plan' returns a 'dict', but the response variable 'workout_plan' is declared as type 'str'."
            }
        },
        "API_Call_Errors": {
            "non_existent_API": {
                "spl": non_existent_API,
                "error_path": "instruction.main_flow.if_block.command7",
                "error_reason": "The API 'fetch_fitness_data' called in COMMAND-7 does not exist in the provided global API_info."
            },
            "extraneous_API_parameters": {
                "spl": extraneous_API_parameters,
                "error_path": "instruction.main_flow.sequential_block1.command2",
                "error_reason": "The API 'get_workout_plan' is called with an unexpected parameter 'duration', which is not defined in the API's specification."
            },
            "missing_API_parameters": {
                "spl": missing_API_parameters,
                "error_path": "instruction.main_flow.if_block.command13",
                "error_reason": "The required parameter 'user' is missing in the call to 'log_feedback'."

            },
            "unhandled_API_return_value": {
                "spl": unhandled_API_return_value,
                "error_path": "instruction.main_flow.sequential_block3.command14",
                "error_reason": "The function 'submit_user_progress' returns a value, but no response variable is specified to store this return value."
            },
            "unexpected_API_return_handling": {
                "spl": unexpected_API_return_handling,
                "error_path": "instruction.main_flow.sequential_block3.command15",
                "error_reason": "The function 'log_daily_activity' does not return any value, but a response variable '_log_result' is specified."
            }
        },
        "Global_Variable_Conflict_Errors": {
            "global_variable_naming_conflict": {
                "spl": global_variable_naming_conflict,
                "error_path": "instruction.main_flow.if_block.command13",
                "error_reason": "The global variable '_user_account_fitness' is used as a response variable, which leads to a naming conflict and potential overwriting of the global variable."
            }
        }
}


def _add_examples(cnlp: str, examples: str) -> str:
    marker = "        [MAIN_FLOW]"
    if cnlp.count(marker) != 1:
        raise ValueError("Expected exactly one MAIN_FLOW in FitnessHealthAdvisor template.")
    return cnlp.replace(marker, f"{examples}\n\n{marker}", 1)


spl_original_with_examples = _add_examples(
    spl_original,
    '''        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    _chosen_workout_type: "strength",
                    _diet_preference: "high-protein",
                    feedback: "great"
                },
                expected-outputs: {
                    _recommendation: "You did an excellent job today! Keep it up!"
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-9, COMMAND-10, COMMAND-11, COMMAND-14
            } </EXPECTED-WORKER-BEHAVIOR>

            <DEFECT-WORKER-BEHAVIOR> {
                Output Generation Error,
                inputs: {
                    _chosen_workout_type: "strength",
                    _diet_preference: "high-protein",
                    feedback: "great"
                },
                defect-outputs: {
                    _recommendation: "No recommendation was generated."
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-4, COMMAND-5, COMMAND-9, COMMAND-10, COMMAND-11, COMMAND-14,
                defect-explanation: The final recommendation is missing despite successful processing.
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]''',
)


spl_original_with_multiple_workers = """
[DEFINE_AGENT: FitnessHealthAdvisor]
    [DEFINE_PERSONA:]
        ROLE: You are a fitness and health assistant providing workout routines and diet plans based on user input.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Share only safe and verified health tips, avoid any content that could harm the user.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WorkoutType = [strength, cardio, flexibility, balance]
        DietPlan = { meals: List[text], total_calories: int }
        WorkoutPlan = { exercises: List[text], duration_in_minutes: int, intensity: text }
        FeedbackResponse = [great, average, poor]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account_fitness: FitnessUserInfo
        _chosen_workout_type: WorkoutType
        _diet_preference: text
        workout_plan: WorkoutPlan
        diet_plan: DietPlan
        feedback: FeedbackResponse
        _recommendation: text
    [END_VARIABLES]

    [DEFINE_WORKER: "Collect user preferences, coordinate workout generation, provide the diet plan, and collect feedback" FitnessRoutineWorkflow]
        [INPUTS]
            REQUIRED <REF>_user_account_fitness</REF>
        [END_INPUTS]

        [OUTPUTS]
            REQUIRED <REF>_recommendation</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [INPUT "What type of workout would you like to focus on? (strength, cardio, flexibility, balance)" VALUE _chosen_workout_type: WorkoutType SET]
                COMMAND-2 [CALL WorkoutPlanWorker WITH {_user_account_fitness: <REF>_user_account_fitness</REF>, _chosen_workout_type: <REF>_chosen_workout_type</REF>} RESPONSE <REF>workout_plan</REF> SET]
                COMMAND-3 [INPUT "Do you have any dietary preferences? (e.g., vegetarian, low-carb, high-protein)" VALUE _diet_preference: text SET]
                COMMAND-4 [CALL get_diet_plan WITH {user: <REF>_user_account_fitness</REF>, preference: <REF>_diet_preference</REF>} RESPONSE diet_plan: DietPlan SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_chosen_workout_type</REF> = "strength"]
                COMMAND-5 [DISPLAY "Your strength training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "cardio"]
                COMMAND-6 [DISPLAY "Your cardio workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "flexibility"]
                COMMAND-7 [DISPLAY "Your flexibility training workout plan includes: <REF>workout_plan</REF>"]
            [ELSEIF <REF>_chosen_workout_type</REF> = "balance"]
                COMMAND-8 [DISPLAY "Your balance training workout plan includes: <REF>workout_plan</REF>"]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-9 [DISPLAY "Your diet plan is: <REF>diet_plan</REF>"]
                COMMAND-10 [INPUT "How would you rate today's fitness plan? (great, average, poor)" VALUE feedback: FeedbackResponse SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>feedback</REF> = "great"]
                COMMAND-11 [COMMAND Set the value of _recommendation to "You did an excellent job today! Keep it up!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "average"]
                COMMAND-12 [COMMAND Set the value of _recommendation to "You did well, but there's room for improvement!" RESULT _recommendation: text SET]
            [ELSEIF <REF>feedback</REF> = "poor"]
                COMMAND-13 [COMMAND Set the value of _recommendation to "Don't be discouraged. Tomorrow is another chance!" RESULT _recommendation: text SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-14 [DISPLAY "Today's feedback: <REF>_recommendation</REF>"]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]

    [DEFINE_WORKER: "Generate a workout plan for the selected workout type" WorkoutPlanWorker]
        [INPUTS]
            REQUIRED <REF>_user_account_fitness</REF>
            REQUIRED <REF>_chosen_workout_type</REF>
        [END_INPUTS]

        [OUTPUTS]
            REQUIRED <REF>workout_plan</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-15 [CALL get_workout_plan WITH {user: <REF>_user_account_fitness</REF>, type: <REF>_chosen_workout_type</REF>} RESPONSE <REF>workout_plan</REF> SET]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""
