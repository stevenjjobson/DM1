const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type WsMessageHandler = {
  onNarrativeChunk: (text: string) => void;
  onNarrativeEnd: () => void;
  onSuggestions: (actions: string[]) => void;
  onTurnComplete: (turn: number) => void;
  onImage: (url: string, caption: string) => void;
  onError: (message: string) => void;
  onConnectionChange: (connected: boolean) => void;
};

export class GameWebSocket {
  private ws: WebSocket | null = null;
  private campaignId: string;
  private token: string;
  private handlers: WsMessageHandler;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

  constructor(campaignId: string, token: string, handlers: WsMessageHandler) {
    this.campaignId = campaignId;
    this.token = token;
    this.handlers = handlers;
  }

  connect(): void {
    this.intentionalClose = false;
    const wsBase = API_BASE.replace(/^http/, "ws");
    const url = `${wsBase}/api/gameplay/ws/${this.campaignId}?token=${this.token}`;

    try {
      this.ws = new WebSocket(url);
    } catch {
      this.handlers.onConnectionChange(false);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.handlers.onConnectionChange(true);
    };

    this.ws.onclose = () => {
      this.handlers.onConnectionChange(false);
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror, which handles reconnection
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleMessage(event);
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendAction(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "action", text }));
    }
  }

  updateToken(token: string): void {
    this.token = token;
  }

  private handleMessage(event: MessageEvent): void {
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }

    switch (data.type) {
      case "narrative_chunk":
        this.handlers.onNarrativeChunk(data.text as string);
        break;
      case "narrative_end":
        this.handlers.onNarrativeEnd();
        break;
      case "suggestions":
        this.handlers.onSuggestions(data.actions as string[]);
        break;
      case "turn_complete":
        this.handlers.onTurnComplete(data.turn as number);
        break;
      case "image":
        this.handlers.onImage(data.url as string, data.caption as string);
        break;
      case "error":
        this.handlers.onError(data.message as string);
        break;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}
