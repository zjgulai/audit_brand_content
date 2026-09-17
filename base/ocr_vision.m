#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#import <AppKit/AppKit.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>

// ocr_vision.m —— 直连系统 Vision.framework 的 OCR CLI
//
// 两种模式：
//   一次一进程：  ocr <图片> [lang...]
//   常驻（B2）：  ocr --serve [lang...]        从 stdin 逐行读路径，逐行回一行 JSON
//
// ★ 为什么加常驻模式：B1 实测「OCR 自己报的处理时间 p50 169ms」，
//   而「本模块实测的墙钟 p50 3573ms」—— 差值里有一大块是**每次起一个子进程**。
//   批量跑图时那是纯浪费。常驻模式只把这一块拿掉，**识别逻辑一行没改**：
//   同一段 `VNRecognizeTextRequest` 配置，同一个 JSON 形状。
//
// ★ 为什么要用 flush：stdout 接管道时是全缓冲的。不 flush 的话调用方
//   读到的是 4KB 一块的乱序结果，看起来像「OCR 卡住了」。

static NSString *jsonEscape(NSString *s) {
  NSMutableString *o = [NSMutableString stringWithCapacity:s.length + 8];
  for (NSUInteger i = 0; i < s.length; i++) {
    unichar c = [s characterAtIndex:i];
    if (c == '\\') [o appendString:@"\\\\"];
    else if (c == '"') [o appendString:@"\\\""];
    else if (c == '\n') [o appendString:@" "];
    else if (c == '\r') [o appendString:@" "];
    else if (c == '\t') [o appendString:@" "];
    else if (c < 0x20) [o appendFormat:@"\\u%04x", c];
    else [o appendFormat:@"%C", c];
  }
  return o;
}

static NSString *ocrOne(NSString *path, NSArray *langs) {
  NSImage *img = [[NSImage alloc] initWithContentsOfFile:path];
  if (!img) return @"{\"ok\":false,\"error\":\"cannot_load_image\"}";
  CGImageRef cg = [img CGImageForProposedRect:NULL context:nil hints:nil];
  if (!cg) return @"{\"ok\":false,\"error\":\"no_cgimage\"}";
  VNRecognizeTextRequest *req = [[VNRecognizeTextRequest alloc] init];
  req.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
  req.recognitionLanguages = langs;
  req.usesLanguageCorrection = YES;
  VNImageRequestHandler *h = [[VNImageRequestHandler alloc] initWithCGImage:cg options:@{}];
  NSDate *t0 = [NSDate date];
  NSError *err = nil;
  if (![h performRequests:@[req] error:&err]) {
    // ★ 失败时也要报出尺寸：实盘里 `perform_failed` 有一类**不是「读不出来」**，
    //   而是「**本来就没有东西可读**」—— Shopify 的 `preview_images/*.thumbnail.0000*`
    //   是 **1×1 像素**的懒加载占位图（实测 2/120）。带出 w/h，
    //   调用方就能把这一类**分类**出来，而不是笼统记成 OCR 失败。
    return [NSString stringWithFormat:
      @"{\"ok\":false,\"error\":\"perform_failed\",\"w\":%zu,\"h\":%zu}",
      CGImageGetWidth(cg), CGImageGetHeight(cg)];
  }
  long ms = (long)(-[t0 timeIntervalSinceNow] * 1000.0);
  NSMutableArray *items = [NSMutableArray array];
  for (VNRecognizedTextObservation *obs in req.results) {
    VNRecognizedText *top = [[obs topCandidates:1] firstObject];
    if (!top) continue;
    CGRect bb = obs.boundingBox;
    [items addObject:[NSString stringWithFormat:
      @"{\"t\":\"%@\",\"c\":%.3f,\"x\":%.4f,\"y\":%.4f,\"w\":%.4f,\"h\":%.4f}",
      jsonEscape(top.string), top.confidence, bb.origin.x, bb.origin.y,
      bb.size.width, bb.size.height]];
  }
  return [NSString stringWithFormat:
    @"{\"ok\":true,\"w\":%zu,\"h\":%zu,\"ms\":%ld,\"n\":%lu,\"lines\":[%@]}",
    CGImageGetWidth(cg), CGImageGetHeight(cg), ms, (unsigned long)items.count,
    [items componentsJoinedByString:@","]];
}

static void emit(NSString *s) {
  fputs([s UTF8String], stdout);
  fputc('\n', stdout);
  fflush(stdout);                       // ★ 不 flush 就会看起来像卡住
}

int main(int argc, const char** argv) {
  @autoreleasepool {
    BOOL serve = (argc >= 2 && strcmp(argv[1], "--serve") == 0);
    // 两种模式下 argv[1] 都是「模式或路径」，语言参数一律从 argv[2] 起。
    NSMutableArray *langs = [NSMutableArray array];
    for (int i = 2; i < argc; i++) {
      [langs addObject:[NSString stringWithUTF8String:argv[i]]];
    }
    if (langs.count == 0) { [langs addObject:@"zh-Hans"]; [langs addObject:@"en-US"]; }

    if (!serve) {
      if (argc < 2) { fprintf(stderr, "用法: ocr <图片> [lang...]\n  或: ocr --serve [lang...]\n"); return 2; }
      emit(ocrOne([NSString stringWithUTF8String:argv[1]], langs));
      return 0;
    }

    // ── 常驻：逐行读路径，逐行回结果。**一行请求一行响应**，顺序严格对应。
    char *line = NULL;
    size_t cap = 0;
    ssize_t n;
    while ((n = getline(&line, &cap, stdin)) != -1) {
      while (n > 0 && (line[n-1] == '\n' || line[n-1] == '\r')) line[--n] = '\0';
      if (n == 0) continue;
      if (strcmp(line, "__quit__") == 0) break;
      @autoreleasepool {
        NSString *p = [NSString stringWithUTF8String:line];
        if (!p) { emit(@"{\"ok\":false,\"error\":\"bad_path_encoding\"}"); continue; }
        emit(ocrOne(p, langs));
      }
    }
    free(line);
  }
  return 0;
}
