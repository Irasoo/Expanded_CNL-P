spl_travel_assistant = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

persona_referenced_global_variable_does_not_exist = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute, the specific tasks information is subject to <REF>_task_info</REF>.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

constraint_referenced_global_variable_does_not_exist = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content, for details regarding the explanation of prohibited content, please refer to <REF>_description_of_violations</REF>.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_undeclared_variable_reference_in_para = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_undeclared_variable_reference = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo 
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [DISPLAY "Your transportation mode is: " <REF>transport_mode</REF>]
                COMMAND-2 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-3 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-7 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-8 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-9 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_duplicate_variable_declaration = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _current_weather: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_current_weather</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_variable_referenced_before_declaration = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [DISPLAY "Your transportation mode is: " <REF>transport_mode</REF>]
                COMMAND-2 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-3 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-7 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-8 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-9 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

instruction_conditional_branch_scope_issue = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Cloudy, Windy]
        TransportMode = [Walking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
        _non_transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _non_transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

target_type_cannot_be_found = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        Transport_Mode = [Walking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

API_call_argument_type_mismatch = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account3: text
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account3</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account3</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account3</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

non_existent_API = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_travel_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

API_return_type_mismatch = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: text
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: text SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

extraneous_API_parameters = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Cloudy, Windy]
        TransportMode = [Walking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _date: text
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
            <REF>_date</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>, date: <REF>_date</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

missing_API_parameters = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Cloudy, Windy]
        TransportMode = [Walking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _date: text
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
            <REF>_date</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_travel_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

unhandled_API_return_value = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]
    
    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]
    
    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Cloudy, Windy]
        TransportMode = [Walking, PublicTransport, Driving, StayHome]
    [END_TYPES]
    
    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]
    
    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]
    
        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]
    
        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>}]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]
    
            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]
    
            [SEQUENTIAL_BLOCK]
                COMMAND-5 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

unexpected_API_return_handling = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]
    
    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content
    [END_CONSTRAINTS]
    
    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Cloudy, Windy]
        TransportMode = [Walking, PublicTransport, Driving, StayHome]
    [END_TYPES]
    
    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
        _log_result: text
    [END_VARIABLES]
    
    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]
    
        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]
    
        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _weather_info: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]
    
            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]
    
            [SEQUENTIAL_BLOCK]
                COMMAND-5 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} RESPONSE _log_result: text SET]
                COMMAND-6 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""

global_variable_naming_conflict = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on weather and user preferences.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Workflow to suggest transportation mode" TravelWorkflow]
        [INPUTS]
            <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE _user_account1: dict SET]
                COMMAND-2 [CALL extract_weather_condition WITH {weather_data: <REF>_user_account1</REF>} RESPONSE _current_weather: WeatherCondition SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-6 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-7 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-8 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
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
                "error_reason": "The variable _task_info referenced in <REF>_task_info</REF> is not declared in the DEFINE_VARIABLES section or globally. This leads to an undefined reference."
            }
        }
    },
    "Constraints": {
        "Reference_Related_Errors": {
            "referenced_global_variable_does_not_exist": {
                "spl": constraint_referenced_global_variable_does_not_exist,
                "error_path": "constraints.FORBID.reference1",
                "error_reason": "This variable '_description_of_violations' is not declared"
            }
        }
    },
    "Instruction": {
        "Scope_Related_Errors": {
            "undeclared_variable_reference": [
                {
                    "spl": instruction_undeclared_variable_reference_in_para,
                    "error_path": "instruction.main_flow.sequential_block2.command8",
                    "error_reason": "The variable <REF>transport_mode</REF> referenced in COMMAND-8 is not declared. The correct variable should be <REF>_transport_mode</REF> as declared in DEFINE_VARIABLES.",
                },
                {
                    "spl": instruction_undeclared_variable_reference,
                    "error_path": "instruction.main_flow.sequential_block1.command1.description_with_reference.reference2",
                    "error_reason": "The variable transport_mode referenced in <REF>transport_mode</REF> is not declared. The correct variable should be <REF>_transport_mode</REF> as declared in DEFINE_VARIABLES."
                }
            ],
            "duplicate_variable_declaration": {
                "spl": instruction_duplicate_variable_declaration,
                "error_path": "instruction.main_flow.sequential_block1.command2",
                "error_reason": "The variable _current_weather has been declared twice with different types (WeatherCondition and str). This duplication causes a conflict, and the second declaration will not take effect."
            },
            "variable_referenced_before_declaration": {
                "spl": instruction_variable_referenced_before_declaration,
                "error_path": "instruction.main_flow.sequential_block1.command1.description_with_reference.reference1",
                "error_reason": "The variable _current_weather is referenced in COMMAND-1 before it has been assigned a value. The assignment happens in COMMAND-2, so using it before that leads to undefined behavior."
            },
            "conditional_branch_scope_issue": {
                "spl": instruction_conditional_branch_scope_issue,
                "error_path": "instruction.main_flow.sequential_block2.command5",
                "error_reason": "The variable _transport_mode may not have been assigned in all branches of the IF block. Specifically, in the ELSE branch, _transport_mode is not set, leading to potential usage of an uninitialized variable."
            }
        },
        "Type_Related_Errors": {
            "target_type_cannot_be_found": {
                "spl": target_type_cannot_be_found,
                "error_path": "instruction.main_flow.sequential_block2.command8",
                "error_reason": "The type TransportMode used for _transport_mode is not declared in DEFINE_TYPES. This leads to an undefined type error."
            },
            "API_call_argument_type_mismatch": {
                "spl": API_call_argument_type_mismatch,
                "error_path": "instruction.main_flow.sequential_block1.command1",
                "error_reason": "The parameter user is passed as <REF>_user_account3</REF>, which is of type str. However, the API get_weather_data expects user to be of type UserInfo. This type mismatch leads to an error."
            },
            "API_return_type_mismatch": {
                "spl": API_return_type_mismatch,
                "error_path": "instruction.main_flow.sequential_block1.command1",
                "error_reason": "The API get_weather_data returns a dict, but the response variable _weather_info is declared as type str. This mismatch in expected return type causes an error.",
            }
        },
        "API_Call_Errors": {
            "non_existent_API": {
                "spl": non_existent_API,
                "error_path": "instruction.main_flow.sequential_block1.command1",
                "error_reason": "The API get_travel_data called in COMMAND-1 does not exist in the provided global API_info. This leads to an undefined function call."
            },
            "extraneous_API_parameters": {
                "spl": extraneous_API_parameters,
                "error_path": "instruction.main_flow.sequential_block1.command1",
                "error_reason": " The API get_weather_data is called with an unexpected parameter date: '2024-09-21'. This parameter is not defined in the API's specification, leading to an error due to extraneous parameters."
            },
            "missing_API_parameters": {
                "spl": missing_API_parameters,
                "error_path1": "instruction.main_flow.sequential_block1.command1",
                "error_reason1": "Missing required parameter user in the call to get_weather_data",
                "error_path2": "instruction.main_flow.sequential_block2.command6",
                "error_reason2": "Missing required parameter user in the call to log_transport_suggestion."
            },
            "unhandled_API_return_value": {
                "spl": unhandled_API_return_value,
                "error_path": "instruction.main_flow.sequential_block1.command1",
                "error_reason": "The function get_weather_data returns a value of type dict, but no response variable is specified to store this return value. This leads to an unhandled API return value."
            },
            "unexpected_API_return_handling": {
                "spl": unexpected_API_return_handling,
                "error_path": "instruction.main_flow.sequential_block2.command5",
                "error_reason": "The function log_transport_suggestion does not return any value (returns None), but a response variable _log_result is specified. This leads to unexpected API return handling."
            }
        },
        "Global_Variable_Conflict_Errors": {
            "global_variable_naming_conflict": {
                "spl": global_variable_naming_conflict,
                "error_path": "instruction.main_flow.sequential_block1.command1",
                "error_reason": "There is a naming conflict due to the use of _user_account1 as a response variable in COMMAND-1, which is also a global variable of type UserInfo. This overwrites the global variable and leads to unexpected behavior."
            }
        }
    }
}


def _add_examples(cnlp: str, examples: str) -> str:
    marker = "        [MAIN_FLOW]"
    if cnlp.count(marker) != 1:
        raise ValueError("Expected exactly one MAIN_FLOW in TravelAssistant template.")
    return cnlp.replace(marker, f"{examples}\n\n{marker}", 1)


spl_travel_assistant_with_examples = _add_examples(
    spl_travel_assistant,
    '''        [EXAMPLES]
            <EXPECTED-WORKER-BEHAVIOR> {
                inputs: {
                    _current_weather: "Sunny"
                },
                expected-outputs: {
                    _transport_mode: "Walking"
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-7, COMMAND-8
            } </EXPECTED-WORKER-BEHAVIOR>

            <DEFECT-WORKER-BEHAVIOR> {
                Output Generation Error,
                inputs: {
                    _current_weather: "Sunny"
                },
                defect-outputs: {
                    _transport_mode: "Driving"
                },
                execution-path: COMMAND-1, COMMAND-2, COMMAND-3, COMMAND-7, COMMAND-8,
                defect-explanation: The displayed transport mode does not match the selected mode.
            } </DEFECT-WORKER-BEHAVIOR>
        [END_EXAMPLES]''',
)


spl_travel_assistant_with_multiple_workers = """
[DEFINE_AGENT: TravelAssistant]
    [DEFINE_PERSONA:]
        ROLE: You are a travel assistant helping users plan their commute.
        FUNCTION: Provide transportation suggestions based on current weather information.
    [END_PERSONA]

    [DEFINE_CONSTRAINTS:]
        FORBID: Please do not generate illegal content.
    [END_CONSTRAINTS]

    [DEFINE_TYPES:]
        WeatherCondition = [Sunny, Rainy, Snowy, Cloudy, Windy]
        TransportMode = [Walking, Biking, PublicTransport, Driving, StayHome]
    [END_TYPES]

    [DEFINE_VARIABLES:]
        _user_account1: UserInfo
        _weather_info: dict
        _current_weather: WeatherCondition
        _transport_mode: TransportMode
    [END_VARIABLES]

    [DEFINE_WORKER: "Coordinate weather analysis and recommend a transportation mode" TravelWorkflow]
        [INPUTS]
            REQUIRED <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            REQUIRED <REF>_transport_mode</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-1 [CALL WeatherAnalysisWorker WITH {_user_account1: <REF>_user_account1</REF>} RESPONSE <REF>_current_weather</REF> SET]
            [END_SEQUENTIAL_BLOCK]

            [IF <REF>_current_weather</REF> = "Sunny"]
                COMMAND-2 [COMMAND Set the value of _transport_mode to "Walking" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Rainy"]
                COMMAND-3 [COMMAND Set the value of _transport_mode to "PublicTransport" RESULT _transport_mode: TransportMode SET]
            [ELSEIF <REF>_current_weather</REF> = "Snowy"]
                COMMAND-4 [COMMAND Set the value of _transport_mode to "StayHome" RESULT _transport_mode: TransportMode SET]
            [ELSE]
                COMMAND-5 [COMMAND Set the value of _transport_mode to "Driving" RESULT _transport_mode: TransportMode SET]
            [END_IF]

            [SEQUENTIAL_BLOCK]
                COMMAND-6 [DISPLAY "Based on the current weather, we suggest: " <REF>_transport_mode</REF>]
                COMMAND-7 [CALL log_transport_suggestion WITH {user: <REF>_user_account1</REF>, mode: <REF>_transport_mode</REF>} ]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]

    [DEFINE_WORKER: "Retrieve the user's weather data and extract its current weather condition" WeatherAnalysisWorker]
        [INPUTS]
            REQUIRED <REF>_user_account1</REF>
        [END_INPUTS]

        [OUTPUTS]
            REQUIRED <REF>_current_weather</REF>
        [END_OUTPUTS]

        [MAIN_FLOW]
            [SEQUENTIAL_BLOCK]
                COMMAND-8 [CALL get_weather_data WITH {user: <REF>_user_account1</REF>} RESPONSE <REF>_weather_info</REF> SET]
                COMMAND-9 [CALL extract_weather_condition WITH {weather_data: <REF>_weather_info</REF>} RESPONSE <REF>_current_weather</REF> SET]
            [END_SEQUENTIAL_BLOCK]
        [END_MAIN_FLOW]
    [END_WORKER]
[END_AGENT]
"""
