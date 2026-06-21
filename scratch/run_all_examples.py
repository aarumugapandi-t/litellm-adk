import os
import sys
import subprocess

EXAMPLES_DIR = r"d:\KiBO\litellm-adk\examples"

# These examples might require interactive input or heavy setups.
# We will run them using a script that pipes "y\ny\n" to them.
def run_all():
    examples = [f for f in os.listdir(EXAMPLES_DIR) if f.endswith('.py')]
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    failed = []
    
    for ex in examples:
        print(f"Running {ex}...")
        path = os.path.join(EXAMPLES_DIR, ex)
        
        try:
            # Pass "y\ny\ny\n" to handle any approval prompts
            process = subprocess.run(
                [sys.executable, path],
                input="y\ny\ny\n",
                text=True,
                env=env,
                capture_output=True,
                timeout=20 # 20 seconds timeout per example
            )
            if process.returncode != 0:
                print(f"[{ex}] FAILED with return code {process.returncode}")
                print(process.stderr)
                failed.append(ex)
            else:
                print(f"[{ex}] PASSED")
        except subprocess.TimeoutExpired:
            print(f"[{ex}] TIMED OUT")
            failed.append(ex)
        except Exception as e:
            print(f"[{ex}] ERROR: {e}")
            failed.append(ex)
            
    if failed:
        print(f"\nFailed examples: {failed}")
    else:
        print("\nAll examples passed!")

if __name__ == "__main__":
    run_all()
