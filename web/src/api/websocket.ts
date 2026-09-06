export type WorkflowEventListener = (event: any) => void;

export class ExecutionStreamClient {
  private ws: WebSocket | null = null;
  private listeners: Set<WorkflowEventListener> = new Set();
  private executionId: string | null = null;
  private isClosedManually = false;

  connect(executionId: string) {
    this.executionId = executionId;
    this.isClosedManually = false;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/api/v1/executions/${executionId}/stream`;

    this.ws = new WebSocket(url);

    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        for (const listener of this.listeners) {
          listener(parsed);
        }
      } catch (err) {
        console.error("Error parsing WebSocket event:", err);
      }
    };

    this.ws.onerror = (err) => {
      console.warn("WebSocket error:", err);
    };

    this.ws.onclose = () => {
      if (!this.isClosedManually) {
        // Optional reconnect attempt or completion
      }
    };
  }

  subscribe(listener: WorkflowEventListener) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  disconnect() {
    this.isClosedManually = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const streamClient = new ExecutionStreamClient();
