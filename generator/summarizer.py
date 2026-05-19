from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL

client = Groq(api_key=GROQ_API_KEY)

# ─── Format prompts ───────────────────────────────────────────────────────────

PROMPTS = {

    "mom": """You are a professional meeting secretary.
Given the meeting transcript below, produce Minutes of Meeting (MOM) in this exact structure:

**MINUTES OF MEETING**
Date: [extract if mentioned, else write "Not mentioned"]
Attendees: [list all speakers/names mentioned]

**AGENDA**
[list main topics discussed]

**KEY DECISIONS**
[bullet list — only firm decisions made, not discussions]

**ACTION ITEMS**
[table format: | Action | Owner | Deadline |]
[extract every task assigned to someone]

**KEY DISCUSSION POINTS**
[important points discussed, 5-8 bullets]

**RISKS / CONCERNS RAISED**
[any problems or risks mentioned]

Rules:
- Be specific, not vague
- If something is unclear, write [unclear] not a guess
- Do not add information not in the transcript
""",

    "summary": """You are a meeting analyst.
Given the transcript, write a concise meeting summary:

**MEETING SUMMARY**

**One-line purpose:** [what this meeting was about in one sentence]

**What was discussed:** [3-5 sentences covering main topics]

**Conclusions reached:** [what was decided or agreed upon]

**What happens next:** [next steps mentioned]

Keep it under 300 words. Be direct and clear.
""",

    "transcript": """You are a transcript editor.
Clean up this meeting transcript:
- Fix obvious speech-to-text errors
- Format as: [Speaker/Timestamp]: Text
- Remove filler words (um, uh, like) but keep meaning intact
- Group consecutive lines from same speaker
- Keep all content — do not summarize

Return only the cleaned transcript, nothing else.
""",

    "action_items": """You are a project manager assistant.
Extract ONLY action items from this meeting transcript.

Format as:
**ACTION ITEMS**

| # | Task | Assigned To | Deadline | Priority |
|---|------|------------|----------|----------|
[fill each row]

Priority: High / Medium / Low based on context clues.
If no owner mentioned, write "Unassigned".
If no deadline mentioned, write "Not specified".

After the table, list any FOLLOW-UP QUESTIONS that were left unanswered.

If no action items found, say "No action items identified in this transcript."
""",

    "custom": """You are a meeting analysis assistant.
Analyze the meeting transcript below and follow this instruction exactly:

{custom_instruction}

Be specific and ground everything in what was actually said in the transcript.
Do not add information not present in the transcript.
"""
}


def generate_output(transcript: str, format_type: str, custom_instruction: str = "") -> dict:
    """
    Generate structured output from transcript using Groq LLM.
    format_type: "mom" | "summary" | "transcript" | "action_items" | "custom"
    Returns {"ok": True, "content": "...", "highlights": [...]}
    """
    if not GROQ_API_KEY:
        return {"ok": False, "error": "GROQ_API_KEY not set. Add it to your .env file."}

    if not transcript.strip():
        return {"ok": False, "error": "Transcript is empty."}

    # Pick prompt
    if format_type == "custom":
        if not custom_instruction.strip():
            return {"ok": False, "error": "Please provide a custom instruction."}
        system_prompt = PROMPTS["custom"].format(custom_instruction=custom_instruction)
    else:
        system_prompt = PROMPTS.get(format_type, PROMPTS["summary"])

    # Truncate transcript if too long (Groq 8192 token limit)
    # Rough: 1 word ≈ 1.3 tokens, keep ~5000 words
    words = transcript.split()
    if len(words) > 5000:
        transcript = " ".join(words[:5000])
        transcript += "\n\n[Transcript truncated for length — first 5000 words processed]"

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"TRANSCRIPT:\n\n{transcript}"}
            ],
            temperature=0.2,
            max_tokens=2048,
        )

        content = response.choices[0].message.content.strip()

        # Extract highlights — lines with ** or key markers
        highlights = extract_highlights(content, format_type)

        return {
            "ok": True,
            "content": content,
            "highlights": highlights,
            "tokens_used": response.usage.total_tokens
        }

    except Exception as e:
        return {"ok": False, "error": f"LLM generation failed: {str(e)}"}


def extract_highlights(content: str, format_type: str) -> list:
    """
    Extract lines that should be highlighted in the output doc.
    Returns list of {"text": "...", "type": "decision|action|risk|key"}
    """
    highlights = []
    lines = content.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Decisions → yellow
        if any(kw in line.lower() for kw in ["decided", "agreed", "confirmed", "approved", "will be", "shall"]):
            highlights.append({"text": line, "type": "decision"})

        # Action items → green
        elif any(kw in line.lower() for kw in ["action:", "todo", "task:", "assigned", "will do", "to do", "follow up"]):
            highlights.append({"text": line, "type": "action"})

        # Risks → red
        elif any(kw in line.lower() for kw in ["risk", "concern", "issue", "problem", "blocker", "delay", "challenge"]):
            highlights.append({"text": line, "type": "risk"})

        # Bold lines → key points
        elif line.startswith("**") and line.endswith("**") and len(line) > 4:
            highlights.append({"text": line.strip("*").strip(), "type": "key"})

    return highlights
