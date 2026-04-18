"""
groq_client.py
--------------
Groq API ka connection setup karta hai.
LLaMA 3 model use karta hai - fast aur free!
"""

import os
from groq import Groq
from dotenv import load_dotenv

# .env file se API key load karo
load_dotenv()


def get_groq_client():
    """
    Groq client return karta hai.
    Pehle .env se key dhundhe, nahi mila to error do.
    """
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY nahi mili! "
            ".env file mein GROQ_API_KEY=your_key_here likho."
        )

    return Groq(api_key=api_key)


def groq_chat(prompt: str, system_prompt: str = None, model: str = "llama-3.3-70b-versatile") -> str:
    """
    Groq se simple chat karo.

    Args:
        prompt: User ka message / question
        system_prompt: AI ko role dene ke liye (optional)
        model: Groq model name (default: llama3-70b-8192)

    Returns:
        AI ka response string
    """
    client = get_groq_client()

    messages = []

    # System prompt add karo agar diya ho
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # User ka message add karo
    messages.append({
        "role": "user",
        "content": prompt
    })

    # Groq API call karo
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,       # 0 = consistent, 1 = creative
        max_tokens=2048,       # Response ki max length
    )

    # Sirf text return karo
    return response.choices[0].message.content


# ---- Test karne ke liye ----
if __name__ == "__main__":
    result = groq_chat(
        prompt="Hello! Kya tum mujhe Python ke baare mein batao?",
        system_prompt="Tum ek helpful AI assistant ho jo Hinglish mein baat karta hai."
    )
    print("Groq Response:", result)
