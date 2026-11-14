#!/usr/bin/env python3
"""
纯窗口零杂物自动录屏工具（macOS WindowID 隔离抓取）
支持普通桌面窗口与右上角菜单栏弹窗 App，自动隔离背景桌面与聊天框等无关元素，
输出高清 MP4 或轻量公众号/文档动图 GIF。
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

SWIFT_CAPTURE = r"""
import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

let args = CommandLine.arguments
func argVal(_ flag: String, default defVal: String = "") -> String {
    if let i = args.firstIndex(of: flag), i + 1 < args.count { return args[i + 1] }
    return defVal
}

let appName = argVal("--app")
let isMenubar = args.contains("--menubar")
let outDir = argVal("--out-dir")
let clicksRaw = argVal("--clicks")
let scrollSteps = Int(argVal("--scroll-steps", default: "6")) ?? 6
let scrollDy = Int32(argVal("--scroll-dy", default: "-28")) ?? -28
let holdFrames = Int(argVal("--hold-frames", default: "4")) ?? 4

guard let app = NSWorkspace.shared.runningApplications.first(where: {
    ($0.localizedName ?? "").contains(appName) || ($0.executableURL?.lastPathComponent ?? "").contains(appName)
}) else {
    fputs("❌ 未找到运行中的应用: \(appName)\n", stderr)
    exit(1)
}
let pid = app.processIdentifier
var extrasRef: CFTypeRef?
if isMenubar {
    let axApp = AXUIElementCreateApplication(pid)
    AXUIElementCopyAttributeValue(axApp, "AXExtrasMenuBar" as CFString, &extrasRef)
    if let extras = extrasRef {
        var childrenRef: CFTypeRef?
        AXUIElementCopyAttributeValue(extras as! AXUIElement, kAXChildrenAttribute as CFString, &childrenRef)
        if let children = childrenRef as? [AXUIElement], let first = children.first {
            AXUIElementPerformAction(first, kAXPressAction as CFString)
        }
    }
    Thread.sleep(forTimeInterval: 0.7)
} else {
    app.activate(options: .activateIgnoringOtherApps)
    Thread.sleep(forTimeInterval: 0.4)
}

let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
var targetWID: CGWindowID = 0
var bounds = CGRect.zero
for w in list {
    let wpid = w[kCGWindowOwnerPID as String] as? pid_t ?? 0
    if wpid == pid {
        let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
        let width = b["Width"] as? Double ?? 0
        let height = b["Height"] as? Double ?? 0
        if width > 320 && height > 240 {
            targetWID = w[kCGWindowNumber as String] as? CGWindowID ?? 0
            bounds = CGRect(x: b["X"] as? Double ?? 0, y: b["Y"] as? Double ?? 0, width: width, height: height)
            break
        }
    }
}
guard targetWID != 0 else {
    fputs("❌ 未找到目标可见窗口 (PID=\(pid))\n", stderr)
    exit(2)
}

try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

func snap(_ idx: Int) {
    let proc = Process()
    proc.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    proc.arguments = ["-l", "\(targetWID)", "-x", "-o", "\(outDir)/f_\(String(format: "%04d", idx)).png"]
    try? proc.run()
    proc.waitUntilExit()
}

func clickRel(_ rx: Double, _ ry: Double) {
    let pt = CGPoint(x: bounds.origin.x + bounds.width * rx, y: bounds.origin.y + bounds.height * ry)
    CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
    CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
}

func scroll(_ dy: Int32) {
    let pt = CGPoint(x: bounds.midX, y: bounds.midY)
    CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: pt, mouseButton: .left)?.post(tap: .cghidEventTap)
    CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 1, wheel1: dy, wheel2: 0, wheel3: 0)?.post(tap: .cghidEventTap)
}

var frameIdx = 0
let clickList = clicksRaw.split(separator: ";").compactMap { part -> (Double, Double)? in
    let xy = part.split(separator: ",").compactMap { Double($0.trimmingCharacters(in: .whitespaces)) }
    return xy.count == 2 ? (xy[0], xy[1]) : nil
}

if clickList.isEmpty {
    for _ in 0..<holdFrames { snap(frameIdx); frameIdx += 1; Thread.sleep(forTimeInterval: 0.08) }
    for _ in 0..<scrollSteps { snap(frameIdx); frameIdx += 1; scroll(scrollDy); Thread.sleep(forTimeInterval: 0.08) }
} else {
    for (i, (rx, ry)) in clickList.enumerated() {
        clickRel(rx, ry)
        Thread.sleep(forTimeInterval: 0.25)
        if i == 0 && scrollSteps > 0 {
            for _ in 0..<scrollSteps { snap(frameIdx); frameIdx += 1; scroll(scrollDy); Thread.sleep(forTimeInterval: 0.08) }
        } else {
            for _ in 0..<holdFrames { snap(frameIdx); frameIdx += 1; Thread.sleep(forTimeInterval: 0.09) }
        }
    }
}

if isMenubar, let extras = extrasRef {
    var childrenRef: CFTypeRef?
    AXUIElementCopyAttributeValue(extras as! AXUIElement, kAXChildrenAttribute as CFString, &childrenRef)
    if let children = childrenRef as? [AXUIElement], let first = children.first {
        AXUIElementPerformAction(first, kAXPressAction as CFString)
    }
}
print("CAPTURED_FRAMES=\(frameIdx) WID=\(targetWID)")
"""


def main():
    p = argparse.ArgumentParser(description="纯窗口零杂物自动录屏工具（macOS WindowID 隔离抓取）")
    p.add_argument("--app", required=True, help="应用名或可执行文件名，如 '汇芯内容管家'")
    p.add_argument("--menubar", action="store_true", help="目标为右上角菜单栏弹窗应用")
    p.add_argument("--clicks", default="", help="相对窗口坐标点击序列，如 '0.425,0.148;0.478,0.148;0.530,0.148'")
    p.add_argument("--scroll-steps", type=int, default=6, help="滚动抓帧步数")
    p.add_argument("--scroll-dy", type=int, default=-28, help="每步滚动像素（负数向下）")
    p.add_argument("--hold-frames", type=int, default=5, help="每个点击页面停留帧数")
    p.add_argument("--fps", type=int, default=8, help="输出帧率")
    p.add_argument("--width", type=int, default=900, help="GIF 宽度像素（MP4 默认保持原分辨率偶数对齐）")
    p.add_argument("--out-mp4", default="", help="输出纯窗口 MP4 路径")
    p.add_argument("--out-gif", default="", help="输出轻量动图 GIF 路径")
    args = p.parse_args()

    if not args.out_mp4 and not args.out_gif:
        p.error("请至少指定 --out-mp4 或 --out-gif")

    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        swift_file = td_p / "capture.swift"
        frames_dir = td_p / "frames"
        swift_file.write_text(SWIFT_CAPTURE, encoding="utf-8")

        cmd = [
            "swift", str(swift_file),
            "--app", args.app,
            "--out-dir", str(frames_dir),
            "--clicks", args.clicks,
            "--scroll-steps", str(args.scroll_steps),
            "--scroll-dy", str(args.scroll_dy),
            "--hold-frames", str(args.hold_frames),
        ]
        if args.menubar:
            cmd.append("--menubar")
        subprocess.run(cmd, check=True)

        pattern = str(frames_dir / "f_%04d.png")
        if args.out_mp4:
            Path(args.out_mp4).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "ffmpeg", "-y", "-framerate", str(args.fps), "-i", pattern,
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", args.out_mp4
            ], check=True, capture_output=True)
            print(f"✅ MP4 已导出: {args.out_mp4}")

        if args.out_gif:
            Path(args.out_gif).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "ffmpeg", "-y", "-framerate", str(args.fps), "-i", pattern,
                "-vf", f"scale={args.width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
                args.out_gif
            ], check=True, capture_output=True)
            size_kb = Path(args.out_gif).stat().st_size // 1024
            print(f"✅ GIF 已导出: {args.out_gif} ({size_kb} KB)")


if __name__ == "__main__":
    main()
