from langchain_core.prompts import ChatPromptTemplate


# -------- PLANNER --------
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """
Break the given syllabus into structured topics.

Rules:
- If a line contains ":", treat left as main topic
- If subtopics are separated by ",", split them
- Maintain order
- Cover all content
- Do not add extra topics

Example:
Membership functions: Triangular, Trapezoidal

Output:
Membership Functions - Triangular
Membership Functions - Trapezoidal

Return only a numbered list.
"""),
    ("human", "{syllabus}")
])


# -------- RESEARCHER --------
researcher_prompt = ChatPromptTemplate.from_messages([
    ("system", """
Collect factual information for the topic.

Rules:
- No teaching style
- No formatting
- Include definition, concepts, mechanisms, key details
- Avoid repetition
- Keep concise

Return raw content only.
"""),
    ("human", "Topic: {topic}\nContext: {context}")
])


# -------- WRITER --------
writer_prompt = ChatPromptTemplate.from_messages([
    ("system", """
Convert content into exam-ready notes.

Format (use these exact section labels on their own line):

Definition
Intuition
Detailed Explanation
Example
Key Points

Rules:
- Clear and concise
- Exam-focused
- Do not repeat content
- Do not use asterisks or markdown bold (**)
- Each section must add new information
- Under Key Points, start each line with "- "

Follow format exactly.
"""),
    ("human", "Topic: {topic}\nContent: {research_content}")
])


# -------- CRITIC --------
critic_prompt = ChatPromptTemplate.from_messages([
    ("system", """
Review the notes.

Return PASS only if:
- correct
- complete
- clear
- exam-focused

Otherwise return:
FAIL + specific improvements
"""),
    ("human", "Topic: {topic}\nNotes: {draft_notes}")
])


# -------- EXAM --------
exam_prompt = ChatPromptTemplate.from_messages([
    ("system", """
Generate important exam questions.

Include:
- 2 questions (2 marks)
- 2 questions (5 marks)
- 1 question (10 marks)

Focus on important concepts.
Group by marks.
Do not use asterisks or markdown bold (**).
"""),
    ("human", "Topic: {topic}\nNotes: {final_notes}")
])