/* Utility functions */
function el(s){return document.querySelector(s)}
function els(s){return Array.from(document.querySelectorAll(s))}
function formatTime(iso){if(!iso)return"";try{var c=iso.replace("T"," ").split(".")[0];var p=c.split(" ");if(p.length<2){var d=p[0].split("-");if(d.length===3)return d[1]+"/"+d[2];return iso}var dp=p[0].split("-");var tp=p[1].split(":");if(dp.length>=3&&tp.length>=2)return dp[1]+"/"+dp[2]+" "+tp[0]+":"+tp[1]}catch(e){}return iso}
function escapeHtml(s){if(!s)return"";var d=document.createElement("div");d.appendChild(document.createTextNode(s));return d.innerHTML}
function copyToClipboard(text,btn){if(!text)return;if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(function(){showCopyFeedback(btn)}).catch(function(){fallbackCopy(text,btn)})}else{fallbackCopy(text,btn)}}
function fallbackCopy(text,btn){var ta=document.createElement("textarea");ta.value=text;ta.style.position="fixed";ta.style.left="-9999px";ta.style.top="-9999px";document.body.appendChild(ta);ta.focus();ta.select();try{document.execCommand("copy");showCopyFeedback(btn)}catch(e){showToast("复制失败，请手动复制")}document.body.removeChild(ta)}
function showCopyFeedback(btn){if(!btn)return;btn.classList.add("copied");setTimeout(function(){btn.classList.remove("copied")},1500)}
function showToast(msg,dur){dur=dur||2000;var t=el("#toast");if(!t){t=document.createElement("div");t.id="toast";t.className="toast";document.body.appendChild(t)}t.textContent=msg;t.style.display="block";t.style.opacity="1";clearTimeout(t._t);t._t=setTimeout(function(){t.style.opacity="0";t.style.transition="opacity 0.3s ease";setTimeout(function(){t.style.display="none";t.style.transition=""},300)},dur)}
function debounce(fn,delay){var t=null;return function(){var ctx=this,args=arguments;clearTimeout(t);t=setTimeout(function(){fn.apply(ctx,args)},delay)}}
function uid(){return"uid_"+Math.random().toString(36).substr(2,9)}

/* Simple Markdown-to-HTML renderer */
function renderMarkdown(text) {
    if (!text) return "";
    var html = escapeHtml(text);
    // Headings ### / ## / # (at line start)
    html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');
    // Bold **...**
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Horizontal rule --- (on its own line)
    html = html.replace(/^---+$/gm, '<hr class="md-hr">');
    // Citations [N] or [N,M] — style as subtle superscript
    html = html.replace(/\[(\d+(?:,\d+)*)\]/g, '<sup class="md-cite">[$1]</sup>');
    // Two+ newlines → paragraph break
    html = html.replace(/\n\n+/g, '</p><p class="md-p">');
    // Single newline → line break
    html = html.replace(/\n/g, '<br>');
    // Wrap in paragraph
    html = '<p class="md-p">' + html + '</p>';
    // Clean empty paragraphs
    html = html.replace(/<p class="md-p"><\/p>/g, '');
    return html;
}
