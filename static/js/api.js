/* API wrappers */
function apiFetch(url,options){options=options||{};var h=options.headers||{};if(options.body&&!h["Content-Type"])h["Content-Type"]="application/json";return fetch(url,Object.assign({},options,{headers:h})).then(function(r){if(!r.ok)return r.json().then(function(e){throw new Error(e.detail||"Error "+r.status)}).catch(function(){throw new Error("Error "+r.status)});return r.json()})}
function listSessions(){return apiFetch("/api/conversations")}
function getMessages(sid){return apiFetch("/api/conversations/"+encodeURIComponent(sid)+"/messages")}
function createSession(){return apiFetch("/api/conversations",{method:"POST"})}
function deleteSession(sid){return apiFetch("/api/conversations/"+encodeURIComponent(sid),{method:"DELETE"})}
function searchConversations(q){return apiFetch("/api/tools/search?q="+encodeURIComponent(q))}
function volunteerTool(data){return apiFetch("/api/tools/volunteer",{method:"POST",body:JSON.stringify(data)})}
function quoteTool(data){return apiFetch("/api/tools/quote",{method:"POST",body:JSON.stringify(data)})}
function getConfig(){return apiFetch("/api/config")}
function saveConfig(data){return apiFetch("/api/config",{method:"PUT",body:JSON.stringify(data)})}
function streamChat(msg,session,mode,cb){cb=cb||{};var p=new URLSearchParams({msg:msg,session:session||"new",mode:mode||"agent"});var url="/api/chat/stream?"+p.toString();return fetch(url).then(function(r){if(!r.ok){if(cb.onError)cb.onError("HTTP "+r.status);return}var reader=r.body.getReader();var dec=new TextDecoder("utf-8");var buf="";function pump(){reader.read().then(function(result){if(result.done)return;buf+=dec.decode(result.value,{stream:true});var dbl=String.fromCharCode(10)+String.fromCharCode(10);var parts=buf.split(dbl);buf=parts.pop()||"";for(var i=0;i<parts.length;i++){var block=parts[i].trim();if(!block)continue;var ev="";var dt="";var ls=block.split(String.fromCharCode(10));for(var j=0;j<ls.length;j++){var l=ls[j];if(l.indexOf("event: ")===0)ev=l.slice(7);if(l.indexOf("data: ")===0)dt+=l.slice(6)}if(dt){try{var j=JSON.parse(dt);if(ev==="thinking"&&cb.onThinking)cb.onThinking(j);if(ev==="token"&&cb.onToken)cb.onToken(j);if(ev==="done"&&cb.onDone)cb.onDone(j)}catch(e){}}}pump()})}pump()}).catch(function(e){if(cb.onError)cb.onError(e.message)})}
