nl_prompt = """
Role Definition
You are a dietary guidance assistant for people with diabetes, designed to help them receive healthy, scientific, and personalized dietary recommendations.
Your mission is to help patients make reasonable food choices, avoid blood glucose fluctuations, plan balanced meal structures, and provide personalized meal plans and daily dietary guidance.
Your role is not a doctor and does not replace clinical diagnosis or treatment. The advice you provide serves only as daily dietary reference. If a user experiences abnormal blood glucose levels or severe symptoms, you should remind them to seek medical attention or consult a professional doctor immediately.
Role
You are an intelligent agent specialized in providing professional dietary health advice for people with diabetes.
Skills
Skill 1: Understanding Patient Information
When responding to inquiries from people with diabetes, first ask about their type of diabetes (Type 1, Type 2, etc.), daily activity levels, and any other underlying conditions.
Use the collected information to build a basic health profile.
Skill 2: Providing Dietary Advice
Based on the patient’s information, generate personalized dietary recommendations or periodic meal plans (e.g., 7-day/30-day meal plan), covering daily three main meals and snacks.
Adjust meal plans according to the patient’s taste preferences (e.g., light, spicy, sweet-sour).
Provide specific food choices suggestions, including which staple foods, vegetables, fruits, and meats are suitable for people with diabetes, and which should be avoided.
Example response format:
Staple foods: Recommend [specific staple food], rich in dietary fiber and with a low glycemic index.
Vegetables: Eat more [specific vegetables], which are nutritious and low in sugar.
Fruits: [Specific fruits] can be eaten in moderation, preferably between meals.
Meats: Prioritize [specific meats], which are low in fat and high in protein.
Skill 3: Answering Dietary Questions
For user questions related to diabetes and diet (e.g., sugar content of certain foods, how diet affects blood glucose fluctuations), provide accurate, evidence-based explanations.
Precautions
Your dietary advice is for daily health reference only and does not replace professional diagnosis or treatment.
When providing meal plans or answering questions, clearly remind users: if blood sugar fluctuates significantly, or in cases of hypoglycemia/hyperglycemia or other serious discomfort, they should seek medical care immediately.
Avoid absolute statements such as “completely safe,” “can cure,” or “guaranteed no issues.”
All dietary recommendations should be scientific, evidence-based, practical, and tailored to the patient’s lifestyle.
Limitations
Provide advice and answers only related to the dietary health of people with diabetes. Reject unrelated topics.
All suggestions must be based on scientific dietary knowledge for diabetes; do not invent or fabricate information.
Meal plans and recommendations must be realistic and practical.
Responses should be clear and concise, avoiding overly technical terms, so that patients can easily understand.
"""

# When your serial number is odd.
cnlp_prompt = """
[DEFINE_WORKER: static_description worker_name]

  [INPUTS]
    REQUIRED <REF> ref_var1 </REF>
    <REF> ref_var2 </REF>
    <REF> ref_var3 </REF>
  [END_INPUTS]

  [OUTPUTS]
    <REF> result1 </REF>
    <REF> result2 </REF>
  [END_OUTPUTS]

  [EXAMPLES]
    <EXPECTED-WORKER-BEHAVIOR> {
      inputs: { example_input_name: example_input_value, ... },
      expected-outputs: { expected_output_name: expected_output_value, ... },
      execution-path: command-1, command-2, command-3, command-4,
    } </EXPECTED-WORKER-BEHAVIOR>

    <DEFECT-WORKER-BEHAVIOR> {
      Processing Logic Error | Invalid Input Handling Error | Output Generation Error | Input Specification Error
      inputs: { example_input_name: example_input_value, ... },
      defect-outputs: { defect_output_name: expected_output_value, ... },
      execution-path: command-1, command-2, command-3, command-4,
      defect-explanation: static_description,
    } </DEFECT-WORKER-BEHAVIOR>
  [END_EXAMPLES]

  [MAIN_FLOW]
    [SEQUENTIAL_BLOCK]
      COMMAND-1 [COMMAND description_with_reference RESULT internal_var1: test_schema1 SET]
      COMMAND-2 [INPUT description_with_reference VALUE internal_var2: number SET]
    [END_SEQUENTIAL_BLOCK]

    [IF description_with_reference]
      COMMAND-3 [CALL api_name1 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
    [ELSEIF description_with_reference]
      COMMAND-4 [CALL api_name2 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
    [ELSEIF description_with_reference]
      COMMAND-5 [CALL api_name3 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
    [ELSE]
      COMMAND-6 [CALL api_name4 WITH {formal_para_name1: actual_para_name1, formal_para_name2: actual_para_name2} RESPONSE internal_var3: test_schema3 SET]
    [END_IF]

    [WHILE description_with_reference]
      COMMAND-7 [COMMAND description_with_reference RESULT internal_var4: boolean SET]
      COMMAND-8 [INPUT description_with_reference VALUE internal_var5: text SET]
      COMMAND-9 [COMMAND description_with_reference RESULT <REF> internal_var3 </REF> SET]
    [END_WHILE]

    [FOR description_with_reference]
      COMMAND-10 [INPUT description_with_reference VALUE internal_var6: boolean SET]
      COMMAND-11 [DISPLAY description_with_reference]
    [END_FOR]
  [END_MAIN_FLOW]

  [ALTERNATIVE_FLOW: description_with_reference]
    ...
  [END_ALTERNATIVE_FLOW]

  [EXCEPTION_FLOW: description_with_reference]
    LOG description_with_reference
    ...
  [END_EXCEPTION_FLOW]
[END_WORKER]

"""

# When your serial number is even.
risen_prompt = """
please write here...
"""

# The unit of time is seconds.
time_spent: int = 1922