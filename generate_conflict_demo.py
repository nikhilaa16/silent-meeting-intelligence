"""
Generate a conflict demo meeting audio file using gTTS (Google Text-to-Speech).
This creates a team meeting recording that directly conflicts with the first demo meeting's decisions.
"""
import sys

def install_gtts():
    """Install gTTS if not already available."""
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gtts", "--user", "-q"])

def generate_conflict_audio():
    try:
        from gtts import gTTS
    except ImportError:
        print("Installing gTTS...")
        install_gtts()
        from gtts import gTTS

    meeting_script = """
    Good morning team. Let's get started. We have a couple of important shifts in direction to discuss.
    
    First, regarding the payment gateway. In our last planning session, we decided to go with Razorpay.
    However, our compliance team did a deep dive and found that their onboarding process for international clients
    is going to delay our launch by six weeks.
    As a result, we are reversing our previous decision: we have decided to go with Stripe as our primary payment gateway
    instead of Razorpay. Razorpay will be completely shelved for now.
    
    Priya, since you were working on the Razorpay integration, you'll need to pivot. Can you adjust the tasks?
    
    Yes, I'll switch the SDKs and start setting up Stripe. It should actually be simpler since their API documentation is excellent.
    I can get the Stripe backend integration prototype ready by next Friday.
    
    Great, so Priya will have the Stripe backend integration prototype ready by next Friday.
    
    Next, let's talk about the PDF export feature. Siddharth, we decided last week to use Puppeteer.
    Have you run into any issues there?
    
    Yes, actually. In my initial testing on our staging environment, running headless Chrome via Puppeteer is using
    way too much RAM. It spiked our memory usage by almost three hundred megabytes per request.
    If we scale this to multiple users, it will crash our micro instances.
    
    Okay, so we need to change our approach. What's the alternative?
    
    I recommend we use PDFKit. It's a pure Node.js library, doesn't require launching a browser instance,
    and has a very tiny memory footprint.
    
    Alright, then the decision is: we are migrating our PDF export library choice from Puppeteer to PDFKit.
    Siddharth, can you deliver the prototype using PDFKit by next Thursday instead?
    
    Yes, that should be doable. I'll have the PDFKit prototype completed by next Thursday.
    
    Great. Let's get to work on these pivots. Thanks everyone.
    """

    print("[*] Generating conflict demo meeting audio...")
    print("    This will take about 30 seconds...")

    tts = gTTS(text=meeting_script, lang="en", slow=False)
    output_path = "demo_meeting_conflict.mp3"
    tts.save(output_path)

    import os
    size_kb = os.path.getsize(output_path) / 1024
    print(f"\n[OK] Conflict demo meeting audio created: {output_path} ({size_kb:.0f} KB)")
    print(f"\nThis meeting contains decisions that conflict with the original demo meeting:")
    print(f"   - Decision to go with Stripe instead of Razorpay (direct conflict)")
    print(f"   - Decision to use PDFKit instead of Puppeteer (direct conflict)")
    print(f"\nUpload demo_meeting_conflict.mp3 to the dashboard AFTER uploading the first meeting to showcase cross-meeting conflict detection!")

if __name__ == "__main__":
    generate_conflict_audio()
