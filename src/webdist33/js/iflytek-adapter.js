/*
 * AI.Super-Agent v3.0 — 讯飞星火 原生 WebSocket 适配器
 * 由 agent.js 在 cfg.provider === 'iflytek' 时调用：window.__iflytekChat(cfg, sys, messages, onDelta)
 * 仅依赖浏览器原生 WebSocket + 自实现 HMAC-SHA256（零外部依赖）。
 *
 * 与『spark（OpenAI 兼容）』预设的区别：
 *   - spark：走 https://spark-api-open.xf-yun.com/v1/chat/completions，仅需 APIKey，支持 function calling。
 *   - iflytek（本文件）：走 wss://spark-api.xf-yun.com/v3.1/chat，需 APPID/APIKey/APISecret，原生 WS，
 *     适合需要指定 domain / 私有化部署 / 不走 OpenAI 兼容网关的场景。
 *
 * 配置（写入 config.json 的对应字段）：iflytekAppId / iflytekApiKey / iflytekApiSecret / iflytekDomain（可选）/ iflytekPath（可选）。
 */

(function () {
  'use strict'

  // ---------- 纯 JS SHA-256 + HMAC（无需 crypto.subtle，兼容任何上下文） ----------
  var K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ])

  function sha256Bytes(bytes) {
    var H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19])
    var l = bytes.length
    var withOne = l + 1
    var k = 0
    while ((withOne + k) % 64 !== 56) k++
    var total = withOne + k + 8
    var m = new Uint8Array(total)
    m.set(bytes, 0)
    m[l] = 0x80
    var bitLen = l * 8
    for (var i = 0; i < 8; i++) m[total - 1 - i] = (bitLen >>> (8 * i)) & 0xff
    function rotr(x, n) { return (x >>> n) | (x << (32 - n)) }
    function ch(x, y, z) { return (x & y) ^ (~x & z) }
    function maj(x, y, z) { return (x & y) ^ (x & z) ^ (y & z) }
    function sigma0(x) { return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22) }
    function sigma1(x) { return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25) }
    function g0(x) { return rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3) }
    function g1(x) { return rotr(x, 17) ^ rotr(x, 19) ^ (x >>> 10) }
    var w = new Uint32Array(64)
    for (var off = 0; off < total; off += 64) {
      for (var t = 0; t < 16; t++) {
        w[t] = (m[off + t * 4] << 24) | (m[off + t * 4 + 1] << 16) | (m[off + t * 4 + 2] << 8) | m[off + t * 4 + 3]
      }
      for (t = 16; t < 64; t++) w[t] = (g1(w[t - 2]) + w[t - 7] + g0(w[t - 15]) + w[t - 16]) | 0
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7]
      for (t = 0; t < 64; t++) {
        var T1 = (h + sigma1(e) + ch(e, f, g) + K[t] + w[t]) | 0
        var T2 = (sigma0(a) + maj(a, b, c)) | 0
        h = g; g = f; f = e; e = (d + T1) | 0; d = c; c = b; b = a; a = (T1 + T2) | 0
      }
      H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0
      H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0
    }
    var out = new Uint8Array(32)
    for (var j = 0; j < 8; j++) {
      out[j * 4] = (H[j] >>> 24) & 0xff; out[j * 4 + 1] = (H[j] >>> 16) & 0xff
      out[j * 4 + 2] = (H[j] >>> 8) & 0xff; out[j * 4 + 3] = H[j] & 0xff
    }
    return out
  }

  function hmacSHA256(keyStr, msgStr) {
    var enc = function (s) { var b = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i) & 0xff; return b }
    var key = enc(keyStr)
    if (key.length > 64) key = sha256Bytes(key)
    var pad = new Uint8Array(64)
    pad.set(key, 0)
    var oKey = new Uint8Array(64), iKey = new Uint8Array(64)
    for (var i = 0; i < 64; i++) { oKey[i] = pad[i] ^ 0x5c; iKey[i] = pad[i] ^ 0x36 }
    var msg = enc(msgStr)
    var inner = new Uint8Array(64 + msg.length)
    inner.set(iKey, 0); inner.set(msg, 64)
    var innerHash = sha256Bytes(inner)
    var outer = new Uint8Array(64 + 32)
    outer.set(oKey, 0); outer.set(innerHash, 64)
    return sha256Bytes(outer)
  }

  function bytesToBase64(bytes) {
    var s = ''
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i])
    return btoa(s)
  }

  function domainForModel(model) {
    if (!model) return 'generalv3.5'
    if (model.indexOf('4.0') >= 0) return '4.0Ultra'
    if (model.indexOf('pro-128k') >= 0) return 'pro-128k'
    if (model.indexOf('generalv3.1') >= 0) return 'generalv3.1'
    if (model.indexOf('generalv3') >= 0) return 'generalv3'
    return 'generalv3.5'
  }

  function buildAuthUrl(cfg) {
    var APIKey = cfg.iflytekApiKey || cfg.apiKey || ''
    var APISecret = cfg.iflytekApiSecret || ''
    var appId = cfg.iflytekAppId || ''
    if (!APIKey || !APISecret || !appId) {
      throw new Error('讯飞原生模式需配置 APPID / APIKey / APISecret（在设置面板填写）')
    }
    var host = 'spark-api.xf-yun.com'
    var path = cfg.iflytekPath || '/v3.1/chat'
    var date = new Date().toUTCString()
    var signatureOrigin = 'host: ' + host + '\ndate: ' + date + '\nGET ' + path + ' HTTP/1.1'
    var sigBytes = hmacSHA256(APISecret, signatureOrigin)
    var signature = bytesToBase64(sigBytes)
    var authStr = 'api_key="' + APIKey + '", algorithm="hmac-sha256", headers="host date request-line", signature="' + signature + '"'
    return 'wss://' + host + path + '?authorization=' + encodeURIComponent(authStr) + '&date=' + encodeURIComponent(date)
  }

  window.__iflytekChat = async function (cfg, sys, messages, onDelta) {
    var appId = cfg.iflytekAppId || ''
    var domain = cfg.iflytekDomain || domainForModel(cfg.model)
    var url = buildAuthUrl(cfg)

    var full = []
    if (sys) full.push({ role: 'system', content: sys })
    for (var i = 0; i < messages.length; i++) {
      var m = messages[i]
      if (m.role === 'user' || m.role === 'assistant') full.push({ role: m.role, content: m.content })
    }

    var payload = {
      header: { app_id: appId, uid: 'ai-super-agent', status: 0 },
      parameter: { chat: { domain: domain, temperature: cfg.temperature != null ? cfg.temperature : 0.7, max_tokens: 4096, top_k: 4, auditing: 'default' } },
      payload: { message: { text: full } },
    }

    var finalText = ''
    var done = false
    await new Promise(function (resolve, reject) {
      var ws
      try { ws = new WebSocket(url) } catch (e) { reject(new Error('WebSocket 创建失败：' + e)); return }
      var settled = false
      function finish(err) { if (settled) return; settled = true; if (err) reject(err); else resolve(); }
      ws.onopen = function () { ws.send(JSON.stringify(payload)) }
      ws.onmessage = function (ev) {
        var data
        try { data = JSON.parse(ev.data) } catch (e) { return }
        var header = data.header || {}
        if (header.code !== 0) { finish(new Error('讯飞错误 ' + header.code + '：' + (header.message || ''))); ws.close(); return }
        var choices = (data.payload && data.payload.choices) || {}
        var texts = choices.text || []
        for (var k = 0; k < texts.length; k++) {
          var c = texts[k].content || ''
          finalText += c
          if (onDelta) onDelta(c, finalText)
        }
        if (choices.status === 2) { done = true; finish(null); ws.close() }
      }
      ws.onerror = function () { finish(new Error('讯飞 WebSocket 连接错误')) }
      ws.onclose = function () { if (!done) finish(null) }
    })

    return { role: 'assistant', content: finalText, tool_calls: [] }
  }

  console.log('[AI.Super-Agent] iflytek 原生适配器已加载')
})()
