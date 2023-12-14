function getUrlVars() {
    var vars = {};
    window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m,key,value) {
        vars[key] = value;
    });
    return vars;
}

document.addEventListener("DOMContentLoaded", function(){
    elink = document.getElementById("my_link");
    targetUrl = decodeURIComponent(getUrlVars()["url"])
    elink.href = targetUrl;
    elink.textContent =  targetUrl;
});
