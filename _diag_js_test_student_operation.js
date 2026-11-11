//获取路径
var basePath = CommonUtil.getPlatformPath();


$(document).ready(function(e) {
	//本课程总测试数量
    var allSize = $("#allTestNumInput").text();
    var doneSpan = $("span[name='complete']");
    var guoqi = $("span[name='guoqi']");
    if(doneSpan == null || doneSpan == "" || doneSpan == undefined) {
    	doneSpan = 0;
    } else {
    	doneSpan = doneSpan.size();
    }
    if(guoqi == null || guoqi == "" || guoqi == undefined) {
    	guoqi = 0;
    } else {
    	guoqi = guoqi.size();
    }
    $("#doneNumInput").text(doneSpan);
    $("#undoNumInput").text(parseInt(allSize) - doneSpan - guoqi);
});



