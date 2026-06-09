#!/usr/bin/env python3
"""No-dependency MongoDB JSON backup.

This is intentionally small and read-only. It speaks enough of the MongoDB
wire protocol to list collections and dump documents from an unauthenticated
local MongoDB. It exists for emergency backups when mongodump/pymongo/docker
are not available in the current shell.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import struct
import time
from pathlib import Path
from typing import Any


OP_MSG = 2013


class Bson:
    @staticmethod
    def cstring(buf: bytes, pos: int) -> tuple[str, int]:
        end = buf.index(b"\x00", pos)
        return buf[pos:end].decode("utf-8"), end + 1

    @staticmethod
    def encode_value(key: str, value: Any) -> bytes:
        k = key.encode("utf-8") + b"\x00"
        if isinstance(value, bool):
            return b"\x08" + k + (b"\x01" if value else b"\x00")
        if isinstance(value, int):
            if -(2**31) <= value < 2**31:
                return b"\x10" + k + struct.pack("<i", value)
            return b"\x12" + k + struct.pack("<q", value)
        if isinstance(value, float):
            return b"\x01" + k + struct.pack("<d", value)
        if isinstance(value, str):
            raw = value.encode("utf-8") + b"\x00"
            return b"\x02" + k + struct.pack("<i", len(raw)) + raw
        if isinstance(value, dict):
            return b"\x03" + k + Bson.encode_doc(value)
        if isinstance(value, list):
            return b"\x04" + k + Bson.encode_doc({str(i): v for i, v in enumerate(value)})
        if value is None:
            return b"\x0a" + k
        raise TypeError(f"Unsupported BSON value for {key}: {type(value)!r}")

    @staticmethod
    def encode_doc(doc: dict[str, Any]) -> bytes:
        body = b"".join(Bson.encode_value(k, v) for k, v in doc.items()) + b"\x00"
        return struct.pack("<i", len(body) + 4) + body

    @staticmethod
    def decode_doc(buf: bytes, pos: int = 0) -> tuple[dict[str, Any], int]:
        start = pos
        (length,) = struct.unpack_from("<i", buf, pos)
        pos += 4
        end = start + length
        out: dict[str, Any] = {}
        while pos < end - 1:
            typ = buf[pos]
            pos += 1
            key, pos = Bson.cstring(buf, pos)
            if typ == 0x01:
                out[key] = struct.unpack_from("<d", buf, pos)[0]
                pos += 8
            elif typ == 0x02:
                (ln,) = struct.unpack_from("<i", buf, pos)
                pos += 4
                out[key] = buf[pos:pos + ln - 1].decode("utf-8", "replace")
                pos += ln
            elif typ == 0x03:
                out[key], pos = Bson.decode_doc(buf, pos)
            elif typ == 0x04:
                arr, pos = Bson.decode_doc(buf, pos)
                out[key] = [arr[str(i)] for i in range(len(arr))]
            elif typ == 0x05:
                (ln,) = struct.unpack_from("<i", buf, pos)
                subtype = buf[pos + 4]
                data = buf[pos + 5:pos + 5 + ln]
                out[key] = {"$binary": data.hex(), "subType": f"{subtype:02x}"}
                pos += 5 + ln
            elif typ == 0x07:
                out[key] = {"$oid": buf[pos:pos + 12].hex()}
                pos += 12
            elif typ == 0x08:
                out[key] = bool(buf[pos])
                pos += 1
            elif typ == 0x09:
                (millis,) = struct.unpack_from("<q", buf, pos)
                pos += 8
                when = dt.datetime.fromtimestamp(millis / 1000, tz=dt.timezone.utc)
                out[key] = {"$date": when.isoformat()}
            elif typ == 0x0A:
                out[key] = None
            elif typ == 0x10:
                out[key] = struct.unpack_from("<i", buf, pos)[0]
                pos += 4
            elif typ == 0x11:
                inc, ts = struct.unpack_from("<II", buf, pos)
                out[key] = {"$timestamp": {"t": ts, "i": inc}}
                pos += 8
            elif typ == 0x12:
                out[key] = struct.unpack_from("<q", buf, pos)[0]
                pos += 8
            else:
                raise ValueError(f"Unsupported BSON type 0x{typ:02x} for key {key!r}")
        return out, end


class RawMongo:
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.req_id = 1

    def close(self) -> None:
        self.sock.close()

    def command(self, db: str, command: dict[str, Any]) -> dict[str, Any]:
        req_id = self.req_id
        self.req_id += 1
        body = struct.pack("<I", 0) + b"\x00" + Bson.encode_doc({"$db": db, **command})
        header = struct.pack("<iiii", 16 + len(body), req_id, 0, OP_MSG)
        self.sock.sendall(header + body)
        hdr = self._read_exact(16)
        length, _response_id, _response_to, opcode = struct.unpack("<iiii", hdr)
        if opcode != OP_MSG:
            raise RuntimeError(f"Unexpected opcode {opcode}")
        payload = self._read_exact(length - 16)
        doc, _ = Bson.decode_doc(payload, 5)
        if doc.get("ok") not in (1, 1.0, True):
            raise RuntimeError(f"Mongo command failed: {doc}")
        return doc

    def _read_exact(self, n: int) -> bytes:
        chunks = []
        remaining = n
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("Socket closed while reading Mongo response")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


def dump_collection(client: RawMongo, db: str, name: str) -> list[dict[str, Any]]:
    first = client.command(db, {"find": name, "filter": {}, "batchSize": 500})
    cursor = first["cursor"]
    docs = list(cursor.get("firstBatch", []))
    cursor_id = int(cursor.get("id", 0))
    while cursor_id:
        nxt = client.command(db, {"getMore": cursor_id, "collection": name, "batchSize": 500})
        cursor = nxt["cursor"]
        docs.extend(cursor.get("nextBatch", []))
        cursor_id = int(cursor.get("id", 0))
    return docs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=27017)
    parser.add_argument("--db", default="test_database")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out or f"backups/mongo-{args.db}-{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    client = RawMongo(args.host, args.port)
    try:
        hello = client.command("admin", {"hello": 1})
        names_doc = client.command(args.db, {"listCollections": 1, "nameOnly": True})
        collections = [c["name"] for c in names_doc["cursor"]["firstBatch"]]
        manifest = {
            "database": args.db,
            "host": args.host,
            "port": args.port,
            "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "mongo": {"isWritablePrimary": hello.get("isWritablePrimary"), "maxWireVersion": hello.get("maxWireVersion")},
            "collections": {},
        }
        for coll in collections:
            docs = dump_collection(client, args.db, coll)
            path = out_dir / f"{coll}.json"
            path.write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")
            manifest["collections"][coll] = {"count": len(docs), "file": path.name}
            print(f"{coll}: {len(docs)}")
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"backup_dir={out_dir}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
