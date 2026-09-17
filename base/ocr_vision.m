#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#import <AppKit/AppKit.h>
int main(int argc, const char** argv) {
  @autoreleasepool {
    if (argc < 2) { fprintf(stderr, "用法: ocr <图片> [lang...]\n"); return 2; }
    NSString *p = [NSString stringWithUTF8String:argv[1]];
    NSImage *img = [[NSImage alloc] initWithContentsOfFile:p];
    if (!img) { printf("{\"ok\":false,\"error\":\"cannot_load_image\"}\n"); return 0; }
    CGImageRef cg = [img CGImageForProposedRect:NULL context:nil hints:nil];
    if (!cg) { printf("{\"ok\":false,\"error\":\"no_cgimage\"}\n"); return 0; }
    NSMutableArray *langs = [NSMutableArray array];
    for (int i = 2; i < argc; i++) [langs addObject:[NSString stringWithUTF8String:argv[i]]];
    if (langs.count == 0) { [langs addObject:@"zh-Hans"]; [langs addObject:@"en-US"]; }
    VNRecognizeTextRequest *req = [[VNRecognizeTextRequest alloc] init];
    req.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
    req.recognitionLanguages = langs;
    req.usesLanguageCorrection = YES;
    VNImageRequestHandler *h = [[VNImageRequestHandler alloc] initWithCGImage:cg options:@{}];
    NSDate *t0 = [NSDate date];
    NSError *err = nil;
    if (![h performRequests:@[req] error:&err]) {
      printf("{\"ok\":false,\"error\":\"perform_failed\"}\n"); return 0;
    }
    long ms = (long)(-[t0 timeIntervalSinceNow] * 1000.0);
    NSMutableArray *items = [NSMutableArray array];
    for (VNRecognizedTextObservation *obs in req.results) {
      VNRecognizedText *top = [[obs topCandidates:1] firstObject];
      if (!top) continue;
      NSString *s = [top.string stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"];
      s = [s stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
      s = [s stringByReplacingOccurrencesOfString:@"\n" withString:@" "];
      CGRect bb = obs.boundingBox;
      [items addObject:[NSString stringWithFormat:
        @"{\"t\":\"%@\",\"c\":%.3f,\"x\":%.4f,\"y\":%.4f,\"w\":%.4f,\"h\":%.4f}",
        s, top.confidence, bb.origin.x, bb.origin.y, bb.size.width, bb.size.height]];
    }
    printf("{\"ok\":true,\"w\":%zu,\"h\":%zu,\"ms\":%ld,\"n\":%lu,\"lines\":[%s]}\n",
      CGImageGetWidth(cg), CGImageGetHeight(cg), ms, (unsigned long)items.count,
      [[items componentsJoinedByString:@","] UTF8String]);
  }
  return 0;
}
