// ==UserScript==
// @name         KrakenFiles Auto Link Copier (Violentmonkey)
// @namespace    http://violentmonkey.net/
// @version      10.0
// @description  Automatically extracts link after solving Turnstile, no click required, no downloads.
// @match        *://krakenfiles.com/view/*
// @inject-into  page
// @grant        none
// @run-at       document-idle
// ==/UserScript==
(function() {
    'use strict';
    // The beautiful UI to show the link on mobile
    function showLinkUI(link) {
        try { navigator.clipboard.writeText(link); } catch(e) {}
        var overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:9999999;display:flex;align-items:center;justify-content:center;padding:20px;box-sizing:border-box;';
        
        var box = document.createElement('div');
        box.style.cssText = 'background:#fff;padding:25px;border-radius:15px;width:100%;max-width:500px;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,0.5);font-family:system-ui,Arial,sans-serif;';
        
        var title = document.createElement('h3');
        title.textContent = '\u2705 Link Extracted!';
        title.style.cssText = 'margin-top:0;color:#2e7d32;font-size:22px;';
        
        var desc = document.createElement('p');
        desc.textContent = 'Extracted WITHOUT clicking download! No files were downloaded to your device.';
        desc.style.cssText = 'color:#555;font-size:14px;margin-bottom:15px;';
        
        var textarea = document.createElement('textarea');
        textarea.value = link;
        textarea.readOnly = true;
        textarea.style.cssText = 'width:100%;height:110px;padding:12px;border:2px solid #ccc;border-radius:8px;font-family:monospace;font-size:14px;box-sizing:border-box;margin-bottom:15px;resize:none;word-break:break-all;background:#f9f9f9;color:#000;';
        
        var copyBtn = document.createElement('button');
        copyBtn.textContent = '\uD83D\uDCCB COPY LINK';
        copyBtn.style.cssText = 'background:#1976d2;color:white;border:none;padding:16px;font-size:16px;border-radius:8px;font-weight:bold;cursor:pointer;width:100%;box-shadow:0 4px 6px rgba(0,0,0,0.1);margin-bottom:10px;';
        
        var closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        closeBtn.style.cssText = 'background:transparent;color:#777;border:none;padding:10px;cursor:pointer;text-decoration:underline;font-size:14px;';
        
        copyBtn.onclick = function() {
            textarea.focus();
            textarea.select();
            textarea.setSelectionRange(0, 99999);
            try {
                document.execCommand('copy');
                copyBtn.textContent = '\u2705 COPIED!';
                copyBtn.style.background = '#388e3c';
                setTimeout(function() {
                    copyBtn.textContent = '\uD83D\uDCCB COPY LINK';
                    copyBtn.style.background = '#1976d2';
                }, 2000);
            } catch (err) {
                try { navigator.clipboard.writeText(link); } catch(e) {}
            }
        };
        
        closeBtn.onclick = function() {
            overlay.remove();
        };
        
        box.appendChild(title);
        box.appendChild(desc);
        box.appendChild(textarea);
        box.appendChild(copyBtn);
        box.appendChild(closeBtn);
        overlay.appendChild(box);
        document.body.appendChild(overlay);
    }
    // Function to extract the link
    function extractNow() {
        if (window._kf_extracted) return;
        window._kf_extracted = true;
        console.log("\uD83D\uDD17 Extracting link automatically...");
        var btn = document.querySelector('#dl-form button[type="submit"]');
        if (btn) {
            btn.innerHTML = '\u23F3 Extracting Link...';
            btn.style.opacity = '0.7';
        }
        // Fill userdata exactly as the site expects
        try {
            if (window.behaviorTracker) {
                var c = window.behaviorTracker.getBehavior();
                c.ft = window.behaviorTracker.getPageFocusTime();
                c.fg = window.behaviorTracker.getFocusGaps();
                c.bg = window.behaviorTracker.getBlurDurations();
                c.iw = window.innerWidth;
                c.documentReferrer = document.referrer;
                var ud = document.querySelector('input[name="userdata"]');
                if (ud) ud.value = btoa(JSON.stringify(c));
            }
        } catch(e) {}
        // Make the AJAX request ourselves
        var form = document.getElementById('dl-form');
        var formData = new FormData(form);
        var params = new URLSearchParams();
        
        var entries = formData.entries();
        var entry = entries.next();
        while (!entry.done) {
            params.append(entry.value[0], entry.value[1]);
            entry = entries.next();
        }
        var xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        
        xhr.onload = function() {
            try {
                var j = JSON.parse(xhr.responseText);
                if (j.url) {
                    showLinkUI(j.url);
                } else if (j.msg) {
                    alert('\u274C Error: ' + j.msg);
                    if (btn) btn.innerHTML = 'Error extracting';
                }
            } catch(e) {
                alert('\u274C Failed to parse response');
            }
        };
        xhr.onerror = function() {
            alert('\u274C Network error while extracting');
        };
        
        xhr.send(params.toString());
    }
    // 1. AUTO-EXTRACT: Watch for Cloudflare Turnstile to be solved
    var checkInterval = setInterval(function() {
        if (window._kf_extracted) {
            clearInterval(checkInterval);
            return;
        }
        var cfInput = document.querySelector('[name="cf-turnstile-response"]');
        if (cfInput && cfInput.value && cfInput.value.length > 20) {
            clearInterval(checkInterval);
            extractNow(); // Execute immediately!
        }
    }, 500);
    // 2. FALLBACK BLOCK: If you manually click "Download now", stop it completely
    var form = document.getElementById('dl-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            // STOP the form from submitting normally (this prevents the download)
            e.preventDefault();
            e.stopImmediatePropagation();
            
            // Extract the link instead
            extractNow();
        }, true); // "true" means Capture phase, so this runs BEFORE KrakenFiles code
    }
})();
