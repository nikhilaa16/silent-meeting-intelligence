"""
Generate a demo meeting audio file using gTTS (Google Text-to-Speech).
This creates a realistic 3-minute team meeting recording perfect for demoing
the Silent Meeting Intelligence system.

The meeting is designed to contain:
  - Clear decisions (so the decision extractor has plenty to find)
  - Named action items with deadlines (so action item extractor shines)
  - Open questions (so the open question extractor has material)
  - A realistic team conversation flow
"""
import sys


def install_gtts():
    """Install gTTS if not already available."""
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gtts", "--user", "-q"])


def generate_demo_audio():
    try:
        from gtts import gTTS
    except ImportError:
        print("Installing gTTS...")
        install_gtts()
        from gtts import gTTS

    # ── The Demo Meeting Script ────────────────────────────────────────────────
    # A realistic product team standup / sprint planning meeting
    # Carefully written to have rich decisions, action items, and open questions

    meeting_script = """
    Good morning everyone. Let's get started with our sprint planning meeting.
    We have a lot to cover today so let's keep it focused.

    First, a quick update on where we are. We shipped the user authentication module last week,
    and the QA team has signed off on it. So that is now officially done.

    Regarding the mobile app performance issues that were reported by customers last Thursday,
    we've identified the root cause. It was a memory leak in the image caching library.
    Rahul, can you push the hotfix to production today?

    Yes I will deploy the hotfix by 3 PM today. I've already tested it on staging and it looks good.

    Perfect. So the decision is, we are deploying the image caching hotfix to production today.

    Now let's talk about the upcoming payment gateway integration. We've evaluated Stripe and Razorpay.
    After reviewing the transaction fees and the Indian market penetration, we have decided to go with Razorpay
    as our primary payment gateway. Stripe will be kept as a backup option.

    Priya, you'll be leading the Razorpay integration. What's your timeline?

    I can have the backend API ready by next Friday. But I'll need the design mockups for the payment screens
    from the design team before I can start on the frontend.

    Okay so Priya will complete the Razorpay backend API by next Friday.
    Ananya, can you get the payment screen designs to Priya by Wednesday?

    Wednesday works for me. I'll have the Figma designs ready and shared by Wednesday afternoon.

    Great. So Ananya will deliver the payment screen designs by Wednesday.

    Now, there's still an open question about whether we support UPI payments in the first release
    or push it to version two. We don't have a clear answer on that yet. Can we loop in the product manager
    and get a decision on UPI by end of week?

    Yes I will schedule a call with Meera from product by tomorrow and get clarity on the UPI scope.

    Good. So Vikram will schedule a call with Meera tomorrow to decide on UPI scope.

    Moving on to the analytics dashboard. The client has asked us to add export to PDF functionality.
    We need to decide whether to use a third party library or build it ourselves.
    After discussing with the team, we have decided to use the Puppeteer library for PDF export.
    It's well maintained and will save us at least two weeks of development time.

    Siddharth, can you own the PDF export feature?

    Sure. I'll start on it today. I think I can have a working prototype by next Thursday.

    Perfect. Siddharth will deliver the PDF export prototype by next Thursday.

    One more thing. The server costs for last month came in at forty percent over budget.
    We need to do a cost audit. However, we're not sure yet whether this is because of the new
    machine learning pipeline we deployed or the increase in user traffic.
    We need to investigate before we can take any action.

    I'll pull the AWS cost explorer report and share it with everyone by tomorrow morning.

    That's great, so Rahul will also share the AWS cost breakdown by tomorrow morning.

    Alright, let's quickly summarize. We are deploying the hotfix today.
    We are going with Razorpay for payments.
    Priya is on the backend API by Friday.
    Ananya is on the designs by Wednesday.
    Siddharth is on PDF export by next Thursday.
    Vikram is getting clarity on UPI from product.
    Rahul is sharing the AWS cost report tomorrow.

    The open items are: UPI support decision pending with product, and the root cause of the server cost spike
    is still under investigation.

    Good meeting everyone. Let's get to work. Thanks.
    """

    print("[*] Generating demo meeting audio...")
    print("    This will take about 30 seconds...")

    tts = gTTS(text=meeting_script, lang="en", slow=False)
    output_path = "demo_meeting.mp3"
    tts.save(output_path)

    import os
    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n[OK] Demo meeting audio created: {output_path} ({size_kb:.0f} KB)")
    print(f"\nThis meeting contains:")
    print(f"   - 6 clear decisions")
    print(f"   - 6 action items with owners and deadlines")
    print(f"   - 2 open questions")
    print(f"\nUpload demo_meeting.mp3 to the dashboard to see the magic!")


if __name__ == "__main__":
    generate_demo_audio()
