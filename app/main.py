"""
main.py — চালাও: python main.py
"""
from supervisor import supervisor

if __name__ == "__main__":
    print("🤖 Agno General-Purpose Supervisor System — 'exit' লিখলে বন্ধ হবে")
    print("লোড হওয়া টিম:", [t.name for t in supervisor.members], "\n")
    supervisor.cli_app(stream=True)
