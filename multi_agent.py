import os
import asyncio
import re
import subprocess
from dotenv import load_dotenv
import webbrowser
import platform
import time      # Add this line
import shutil    # Add this line

# Load environment variables from .env file
load_dotenv()

# Fix for Python 3.10 on Windows asyncio event loop issue
if platform.system() == 'Windows':
    # Set the event loop policy to avoid the ProactorEventLoop issues
    if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Alternative fix for older versions
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion

# --- Initialize Kernel
kernel = Kernel()

# Use OpenAI directly (without Azure)
print("Using OpenAI service...")
kernel.add_service(
    AzureChatCompletion(
        deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )
)

def load_system_message(file_path: str) -> str:
    with open(file_path, "r") as f:
        return f.read()

# --- Load system prompts
ba_prompt = load_system_message("skills/BA/system_message.txt")
se_prompt = load_system_message("skills/SE/system_message.txt")
po_prompt = load_system_message("skills/PO/system_message.txt")

# --- Create ChatCompletionAgents
ba_agent = ChatCompletionAgent(
    name="BusinessAnalyst",
    description="Business Analyst persona for gathering and clarifying requirements.",
    kernel=kernel,
    instructions=ba_prompt
)
se_agent = ChatCompletionAgent(
    name="SoftwareEngineer",
    description="Software Engineer persona to implement requested features and produce HTML/JS code.",
    kernel=kernel,
    instructions=se_prompt
)
po_agent = ChatCompletionAgent(
    name="ProductOwner",
    description="Product Owner persona for reviewing and ensuring all requirements are met.",
    kernel=kernel,
    instructions=po_prompt
)

print("All ChatCompletionAgents created successfully:")
print(f"- {ba_agent.name}")
print(f"- {se_agent.name}")
print(f"- {po_agent.name}")

# --- Simple termination function instead of custom class to avoid Pydantic issues
async def should_terminate_conversation(history, max_iterations=30):  # Increased from 15 to 30
    """Simple function to check termination conditions."""
    
    # Count messages to estimate iterations
    iteration_count = len([msg for msg in history if isinstance(msg, ChatMessageContent)])
    
    if iteration_count >= max_iterations:
        print(f"⚠️ Maximum messages ({max_iterations}) reached. Auto-terminating to prevent errors.")
        return True
        
    # Check for user approval
    for msg in history:
        if (
            isinstance(msg, ChatMessageContent) and
            msg.role == AuthorRole.USER and
            "APPROVED" in msg.content.upper()
        ):
            print("✅ Termination condition met: User said APPROVED.")
            return True
            
    return False

# Create group chat without custom termination strategy to avoid Pydantic errors
group_chat = AgentGroupChat(
    agents=[ba_agent, se_agent, po_agent]
)
print("AgentGroupChat created and ready!")

# --- Callback to run after user says APPROVED
async def on_approved_callback():
    print("The user has APPROVED the work! Proceeding with final steps...")
    try:
        # Check if we're on Windows and use appropriate shell
        if platform.system() == 'Windows':
            # For Windows, try different approaches
            try:
                # Try with Git Bash
                result = subprocess.run(
                    ["bash", "./push_to_github.sh"],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=os.getcwd()
                )
            except FileNotFoundError:
                # Fallback to direct execution
                result = subprocess.run(
                    ["./push_to_github.sh"],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=os.getcwd(),
                    shell=True
                )
        else:
            # For Unix/Linux systems
            result = subprocess.run(
                ["./push_to_github.sh"],
                capture_output=True,
                text=True,
                check=True,
                cwd=os.getcwd()
            )
        
        print("✅ Git push successful!")
        if result.stdout:
            print(result.stdout)
            
    except subprocess.CalledProcessError as e:
        print("❌ Error while pushing to GitHub:")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        if e.stdout:
            print(f"Standard output: {e.stdout}")
        print(f"Return code: {e.returncode}")
    except Exception as e:
        print(f"❌ Unexpected error during git push: {str(e)}")

# --- Auto push function (called whenever index.html is generated)
async def auto_push_to_github():
    """Automatically push generated files to GitHub."""
    print("🤖 Auto-pushing generated files to GitHub...")
    
    try:
        # Use direct git commands instead of shell script
        print("🔄 Adding files to git...")
        add_result = subprocess.run(["git", "add", "."], check=True, cwd=os.getcwd())
        print("✅ Files added to git")
        
        # Check if there are changes to commit
        diff_result = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=os.getcwd())
        if diff_result.returncode == 0:
            print("ℹ️ No changes to commit")
            return
        
        # Show what will be committed
        print("📋 Changes to be committed:")
        subprocess.run(["git", "status", "--short"], cwd=os.getcwd())
        
        # Commit changes
        commit_msg = f"Update index.html - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"💾 Committing with message: '{commit_msg}'")
        commit_result = subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=os.getcwd())
        print("✅ Changes committed")
        
        # Push to remote
        print("🚀 Pushing to GitHub...")
        push_result = subprocess.run(["git", "push"], capture_output=True, text=True, check=True, cwd=os.getcwd())
        print("✅ Successfully pushed to GitHub!")
        
        if push_result.stdout:
            print("📤 Push output:")
            print(push_result.stdout)
        
        if push_result.stderr:
            print("📤 Push messages:")
            print(push_result.stderr)
            
        # Show latest commit
        print("📊 Latest commit:")
        subprocess.run(["git", "log", "--oneline", "-1"], cwd=os.getcwd())
        
        # Verify final status
        print("🔍 Final git status:")
        subprocess.run(["git", "status", "--short"], cwd=os.getcwd())
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {str(e)}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Error details: {e.stderr}")
        if hasattr(e, 'stdout') and e.stdout:
            print(f"Output: {e.stdout}")
        
        # Show current status for debugging
        print("🔍 Current git status:")
        subprocess.run(["git", "status"], cwd=os.getcwd())
        
    except Exception as e:
        print(f"❌ Unexpected error during git push: {str(e)}")
        
        # Show current status for debugging
        print("🔍 Current git status:")
        subprocess.run(["git", "status"], cwd=os.getcwd())

# --- Main agent system runner with better HTML extraction
async def run_multi_agent(input_text: str):
    if not input_text.strip():
        print("Input text is empty. Please provide a valid prompt.")
        return

    # Enhance the input to be more specific about HTML output and encourage discussion
    enhanced_input = f"""
{input_text}

CRITICAL WORKFLOW REQUIREMENTS:
1. Business Analyst: Analyze requirements and ask clarifying questions (2-3 exchanges)
2. Product Owner: Define acceptance criteria and review requirements (2-3 exchanges)  
3. Software Engineer: Discuss technical approach and implementation details (2-3 exchanges)
4. ALL AGENTS: Have thorough discussion about the solution (at least 8-10 total exchanges)
5. Software Engineer: MUST provide complete HTML code with CSS and JavaScript

MANDATORY FINAL OUTPUT FORMAT:
The Software Engineer MUST end with exactly this format:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Calculator App</title>
    <style>
        /* CSS styling here */
    </style>
</head>
<body>
    <!-- HTML structure here -->
    <script>
        /* JavaScript functionality here */
    </script>
</body>
</html>
```

DISCUSSION POINTS REQUIRED:
- What features should the calculator have?
- What design/styling approach?
- What JavaScript functionality is needed?
- How should user interactions work?
- What edge cases need handling?

IMPORTANT: 
- Have detailed back-and-forth discussion first
- Software Engineer provides working HTML code last
- Code must be complete and functional
- Use ```html code blocks for the final implementation
"""

    try:
        # Add user message to kick off the conversation
        user_message = ChatMessageContent(
            role=AuthorRole.USER,
            content=enhanced_input
        )
        await group_chat.add_chat_message(user_message)
        print("Added enhanced user message to chat history.")

        print("Streaming responses as they arrive...")
        
        # Add iteration counter for additional safety
        iteration_count = 0
        max_display_iterations = 50  # Increased from 20 to 50 to allow much more conversation
        
        try:
            async for content in group_chat.invoke():
                print(f"# {content.role}: '{content.content}'")
                iteration_count += 1
                
                # DEBUG: Save each message to see what we're getting
                debug_filename = f"debug_msg_{iteration_count}.txt"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(f"Role: {content.role}\n")
                    f.write(f"Content: {content.content}\n")
                print(f"🔍 Saved debug info to {debug_filename}")
                
                # Don't check for HTML too early - let them discuss first
                # Only start looking for HTML after iteration 5 (reduced from 10)
                if iteration_count >= 5:
                    # More aggressive HTML detection
                    content_lower = content.content.lower()
                    has_html = any([
                        "```html" in content_lower,
                        "<!doctype html" in content_lower,
                        "<html" in content_lower and "lang=" in content_lower,
                        "calculator" in content_lower and all(tag in content_lower for tag in ["<div>", "<button>", "<script>"]),
                        "<script>" in content_lower and "<style>" in content_lower,
                        "<head>" in content_lower and "<body>" in content_lower,
                        "function" in content_lower and "<button" in content_lower and "calculator" in content_lower
                    ])
                    
                    if has_html:
                        print("🎯 Found potential HTML code in current message! Processing immediately...")
                        
                        # More comprehensive HTML extraction patterns
                        html_patterns = [
                            r'```html\s*(<!DOCTYPE.*?</html>)\s*```',      # Complete HTML in code block
                            r'```html\s*(.*?</html>)\s*```',               # HTML ending with </html>
                            r'```HTML\s*(<!DOCTYPE.*?</html>)\s*```',      # Uppercase HTML
                            r'```\s*html\s*(<!DOCTYPE.*?</html>)\s*```',   # HTML with spaces
                            r'```\s*(<!DOCTYPE html.*?</html>)\s*```',     # DOCTYPE in any code block
                            r'```[^`]*?(<!DOCTYPE html.*?</html>)[^`]*?```', # DOCTYPE anywhere in code block
                            r'(<!DOCTYPE html.*?</html>)',                 # Raw HTML without code blocks
                            r'```html\s*(.*?)\s*```',                      # Any HTML code block content
                            r'```\s*(.*?calculator.*?</html>)\s*```',      # Calculator-specific content
                        ]
                        
                        html_code = None
                        for i, pattern in enumerate(html_patterns):
                            matches = re.findall(pattern, content.content, re.DOTALL | re.IGNORECASE)
                            if matches:
                                # Take the longest match
                                html_code = max(matches, key=len).strip()
                                print(f"✅ Found HTML using pattern {i+1}: {pattern}")
                                print(f"📄 HTML preview: {html_code[:300]}...")
                                break
                        
                        if html_code and len(html_code) > 200:
                            try:
                                output_path = os.path.join(os.getcwd(), "index.html")
                                
                                # Force delete existing file
                                if os.path.exists(output_path):
                                    os.remove(output_path)
                                    print(f"🗑️ Deleted existing index.html")
                                
                                # Write new HTML
                                with open(output_path, "w", encoding="utf-8") as f:
                                    f.write(html_code)
                                print(f"✅ NEW HTML code saved to: {output_path}")
                                print(f"📁 File size: {len(html_code)} characters")
                                
                                # Verify file was written
                                if os.path.exists(output_path):
                                    with open(output_path, "r", encoding="utf-8") as f:
                                        saved_content = f.read()
                                    print(f"✅ Verified: File contains {len(saved_content)} characters")
                                else:
                                    print("❌ Error: File was not created!")
                                    continue

                                # 🚀 AUTO PUSH TO GITHUB
                                print("🔄 Auto-pushing NEW HTML to GitHub...")
                                await auto_push_to_github()

                                # Open in browser
                                try:
                                    webbrowser.open(f"file://{output_path}")
                                    print("🌐 Opened NEW HTML in browser!")
                                except Exception as browser_error:
                                    print(f"⚠️ Could not open browser: {browser_error}")
                                
                                print("🎉 Successfully generated and saved new HTML!")
                                return  # Exit early since we found and processed HTML
                                
                            except Exception as e:
                                print(f"❌ Error saving HTML: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"⚠️ HTML code too short or empty: {len(html_code) if html_code else 0} characters")
                
                # If we've had enough discussion but no HTML, prompt for it
                if iteration_count == 25 and not has_html:
                    print("🔔 Prompting Software Engineer to provide HTML code...")
                    html_prompt = ChatMessageContent(
                        role=AuthorRole.USER,
                        content="Software Engineer: Please provide the complete HTML code for the calculator now. Use ```html code blocks with DOCTYPE, head, style, body, and script sections."
                    )
                    await group_chat.add_chat_message(html_prompt)
                
                # Safety check to prevent endless display loops
                if iteration_count >= max_display_iterations:
                    print(f"⚠️ Display limit ({max_display_iterations}) reached. Moving to final processing...")
                    break
                    
        except Exception as e:
            print(f"⚠️ Group chat iteration completed or interrupted: {str(e)}")
            print("🔄 Proceeding with message processing...")

        # If we reach here, no HTML was found during streaming
        print("⚠️ No HTML found during conversation streaming.")
        print("🔍 Searching through final message history...")
        
        # Retrieve the final chat history for a final search
        messages = []
        try:
            chat_messages = group_chat.get_chat_messages()
            if hasattr(chat_messages, '__aiter__'):
                async for msg in chat_messages:
                    messages.append(msg)
            else:
                messages = list(chat_messages)
        except Exception as e:
            print(f"⚠️ Error retrieving chat messages: {str(e)}")
            messages = []
        
        print(f"📊 Retrieved {len(messages)} messages from chat history.")

        # Final comprehensive search through all messages
        html_code = None
        print("🔍 Performing comprehensive HTML search...")
        
        for i, msg in enumerate(messages):
            if isinstance(msg, ChatMessageContent) and msg.role == AuthorRole.ASSISTANT:
                content = msg.content
                print(f"📄 Analyzing message {i+1}: {content[:100]}...")
                
                # Look for HTML in multiple ways
                html_indicators = [
                    'html', 'doctype', '<div>', '<button>', 'calculator', 
                    '<script>', '<style>', '<head>', '<body>', 'function'
                ]
                
                if any(indicator in content.lower() for indicator in html_indicators):
                    print(f"🔍 Found HTML indicators in message {i+1}")
                    
                    # Comprehensive HTML extraction patterns
                    html_patterns = [
                        r'```html\s*(<!DOCTYPE.*?</html>)\s*```',
                        r'```html\s*(.*?</html>)\s*```',
                        r'```HTML\s*(<!DOCTYPE.*?</html>)\s*```',
                        r'```\s*html\s*(<!DOCTYPE.*?</html>)\s*```',
                        r'```\s*(<!DOCTYPE html.*?</html>)\s*```',
                        r'(<!DOCTYPE html.*?</html>)',
                        r'(<html.*?</html>)',
                        r'```[^`]*?(<!DOCTYPE html.*?</html>)[^`]*?```',
                        r'```[^`]*?(<html.*?</html>)[^`]*?```',
                        r'```html\s*(.*?)\s*```'  # Any HTML code block
                    ]
                    
                    for j, pattern in enumerate(html_patterns):
                        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                        if matches:
                            # Take the longest match
                            candidate = max(matches, key=len).strip()
                            if len(candidate) > 200:  # Ensure substantial content
                                html_code = candidate
                                print(f"✅ Found HTML code using pattern {j+1} in message {i+1}")
                                print(f"📄 HTML preview: {html_code[:200]}...")
                                break
                    
                    if html_code:
                        break

        if html_code:
            try:
                output_path = os.path.join(os.getcwd(), "index.html")
                
                # Delete existing file instead of backing up
                if os.path.exists(output_path):
                    os.remove(output_path)
                    print(f"🗑️ Deleted existing index.html")
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html_code)
                print(f"✅ HTML code saved to: {output_path}")
                print(f"📁 File size: {len(html_code)} characters")

                # 🚀 AUTO PUSH TO GITHUB
                print("🔄 Auto-pushing generated HTML to GitHub...")
                await auto_push_to_github()

                # Open in browser
                try:
                    webbrowser.open(f"file://{output_path}")
                    print("🌐 Opened in browser!")
                except Exception as browser_error:
                    print(f"⚠️ Could not open browser: {browser_error}")
                    
            except Exception as e:
                print(f"❌ Error writing HTML: {e}")
        else:
            print("❌ No HTML code found in any agent responses.")
            print("🔍 The agents may have discussed the project but didn't provide actual HTML code.")
            
            # Try one more time with a direct request
            print("🔔 Making a direct request for HTML code...")
            try:
                direct_html_request = ChatMessageContent(
                    role=AuthorRole.USER,
                    content="""
Software Engineer: Please provide the complete HTML code for the calculator application now. 

REQUIRED FORMAT:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Calculator</title>
    <style>
        /* Add CSS styling here */
    </style>
</head>
<body>
    <!-- Add calculator HTML structure here -->
    <script>
        /* Add JavaScript functionality here */
    </script>
</body>
</html>
```

Please provide working calculator code with buttons for 0-9, +, -, *, /, =, and clear.
"""
                )
                await group_chat.add_chat_message(direct_html_request)
                
                # Get one more response
                print("🔄 Waiting for HTML response...")
                final_responses = []
                async for final_content in group_chat.invoke():
                    print(f"# {final_content.role}: '{final_content.content}'")
                    final_responses.append(final_content)
                    
                    # Check this final response for HTML
                    if ("```html" in final_content.content.lower() or 
                        "<!doctype html" in final_content.content.lower()):
                        
                        # Try to extract HTML from this final response
                        for pattern in [
                            r'```html\s*(.*?)\s*```',
                            r'```HTML\s*(.*?)\s*```',
                            r'```\s*html\s*(.*?)\s*```',
                            r'(<!DOCTYPE html.*?</html>)',
                            r'(<html.*?</html>)'
                        ]:
                            matches = re.findall(pattern, final_content.content, re.DOTALL | re.IGNORECASE)
                            if matches:
                                final_html = max(matches, key=len).strip()
                                if len(final_html) > 100:
                                    print("✅ Found HTML in final response!")
                                    
                                    # Save the HTML
                                    output_path = os.path.join(os.getcwd(), "index.html")
                                    if os.path.exists(output_path):
                                        os.remove(output_path)
                                        print(f"🗑️ Deleted existing index.html")
                                    
                                    with open(output_path, "w", encoding="utf-8") as f:
                                        f.write(final_html)
                                    print(f"✅ Final HTML saved to: {output_path}")
                                    
                                    # Push to GitHub
                                    await auto_push_to_github()
                                    
                                    # Open in browser
                                    try:
                                        webbrowser.open(f"file://{output_path}")
                                        print("🌐 Opened in browser!")
                                    except Exception as browser_error:
                                        print(f"⚠️ Could not open browser: {browser_error}")
                                    
                                    print("🎉 Successfully generated HTML from final request!")
                                    return messages
                                break
                    
                    # Only process one response to avoid infinite loop
                    break
                    
            except Exception as e:
                print(f"❌ Error in direct HTML request: {str(e)}")
            
            print("💡 Try a more specific prompt like: 'Create a calculator web app with complete HTML, CSS and JavaScript code'")

        print("🏁 Multi-agent workflow completed successfully!")
        return messages

    except Exception as e:
        print(f"❌ Error in run_multi_agent: {str(e)}")
        return []
    finally:
        await asyncio.sleep(0.1)

# --- Async main function with proper cleanup
async def main():
    """Main async function with proper event loop handling."""
    try:
        print("🚀 Multi-Agent System Starting...")
        user_input = input("📝 Please enter your prompt for the multi-agent system: ")
        if user_input.strip():
            await run_multi_agent(user_input)
        else:
            print("❌ Empty input provided. Exiting.")
    except KeyboardInterrupt:
        print("\n⚠️ User interrupted the process. Exiting gracefully.")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("🔍 This might be due to API limits, network issues, or configuration problems.")
    finally:
        # Give time for cleanup
        await asyncio.sleep(0.1)

# --- For running directly with proper event loop handling
if __name__ == "__main__":
    try:
        # Use asyncio.run() which handles event loop creation and cleanup properly
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user.")
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            print("⚠️ Event loop cleanup completed.")
        else:
            print(f"❌ Runtime error: {str(e)}")
    except Exception as e:
        print(f"❌ Final error: {str(e)}")
    finally:
        # Ensure all pending tasks are cancelled
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                pending = asyncio.all_tasks(loop)
                if pending:
                    for task in pending:
                        task.cancel()
                    # Give tasks time to cancel
                    loop.run_until_complete(asyncio.sleep(0.1))
        except Exception:
            # Ignore cleanup errors
            pass
        print("🔚 Application terminated.")