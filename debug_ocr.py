"""Test full-screen OCR via Apple Vision."""
import Quartz
import Vision
import Cocoa
import tempfile, os

# 1. Full screen screenshot
image_ref = Quartz.CGWindowListCreateImage(
    Quartz.CGRectInfinite,
    Quartz.kCGWindowListOptionOnScreenOnly,
    Quartz.kCGNullWindowID,
    Quartz.kCGWindowImageDefault,
)
print(f"Screenshot: {Quartz.CGImageGetWidth(image_ref)}x{Quartz.CGImageGetHeight(image_ref)}")

# 2. Save to temp PNG
tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
tmp.close()
dest = Quartz.CFURLCreateWithFileSystemPath(None, tmp.name, Quartz.kCFURLPOSIXPathStyle, False)
dst = Quartz.CGImageDestinationCreateWithURL(dest, "public.png", 1, None)
Quartz.CGImageDestinationAddImage(dst, image_ref, None)
Quartz.CGImageDestinationFinalize(dst)
print(f"Saved to: {tmp.name} ({os.path.getsize(tmp.name)} bytes)")

# 3. Run Apple Vision OCR
url = Cocoa.NSURL.fileURLWithPath_(tmp.name)
handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
results = []

def completion(req, err):
    if err: print(f"OCR error: {err}"); return
    for obs in req.results():
        t = obs.topCandidates_(1)[0].string()
        if t and t.strip():
            results.append(t.strip())

req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completion)
req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
handler.performRequests_error_([req], None)

print(f"\nOCR found {len(results)} text fragments. First 20:")
for t in results[:20]:
    print(f"  » {t[:120]}")

os.unlink(tmp.name)



