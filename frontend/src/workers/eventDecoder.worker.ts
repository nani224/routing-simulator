/**
 * Web Worker for off-thread MessagePack decoding of PHANTOMNET event stream.
 * Decodes raw binary WebSocket frames or chunked replay streams without blocking the 60 FPS UI.
 */

import { decode } from "@msgpack/msgpack";
import type { EventBatch, PhantomEvent } from "../types/events";

export interface WorkerIncomingMessage {
  type: "DECODE_CHUNK" | "DECODE_EVENTS";
  data: ArrayBuffer | Uint8Array;
}

export interface WorkerOutgoingMessage {
  type: "BATCH_DECODED" | "EVENTS_DECODED" | "DECODE_ERROR";
  batch?: EventBatch;
  events?: PhantomEvent[];
  error?: string;
}

self.onmessage = (e: MessageEvent<WorkerIncomingMessage>) => {
  try {
    const { type, data } = e.data;
    if (type === "DECODE_CHUNK" || type === "DECODE_EVENTS") {
      const uint8 = data instanceof Uint8Array ? data : new Uint8Array(data);
      const decoded = decode(uint8) as unknown;

      if (
        decoded &&
        typeof decoded === "object" &&
        "type" in decoded &&
        (decoded as { type: string }).type === "event_batch"
      ) {
        const batch = decoded as EventBatch;
        self.postMessage({
          type: "BATCH_DECODED",
          batch,
          events: batch.events,
        } satisfies WorkerOutgoingMessage);
      } else if (Array.isArray(decoded)) {
        self.postMessage({
          type: "EVENTS_DECODED",
          events: decoded as PhantomEvent[],
        } satisfies WorkerOutgoingMessage);
      } else if (
        decoded &&
        typeof decoded === "object" &&
        "kind" in decoded
      ) {
        self.postMessage({
          type: "EVENTS_DECODED",
          events: [decoded as PhantomEvent],
        } satisfies WorkerOutgoingMessage);
      }
    }
  } catch (err) {
    self.postMessage({
      type: "DECODE_ERROR",
      error: err instanceof Error ? err.message : String(err),
    } satisfies WorkerOutgoingMessage);
  }
};
