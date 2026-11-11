//获取路径
var basePath = CommonUtil.getPlatformPath();
var ishandsubmit = false;

$(document).ready(function(e) {
	var bts = $(".bank_test").height();
    if($(".record_rate2_in").height()>=50){
		$(".record_rate2_in").css("background-image","url("+basePath+"/resource/test/blue/images/record_accuracy3.png)");
	}else{
		$(".record_rate2_in").css("background-image","url("+basePath+"/resource/test/blue/images/record_accuracy2.png)");
	}	
    var tempateType = $("#templateType", top.window.document).val();
    if (tempateType == 1){
    	if (top.document == parent.document){
        	$(".bank_cont").css("padding","20px");
        	if($(top.window).height() - 215 > bts){
        		$(".bank_test").height($(top.window).height() - 240);
        	}
        	$(top.window).resize(function(){
        		if($(top.window).height() - 215 > bts){
            		$(".bank_test").height($(top.window).height() - 240);
            	}
        	});
		}else{
        	$(".bank_cont").css("padding","0px");
        }
    }

    if (tempateType == 2 || tempateType == 3){
		if (top.document == parent.document){
			$(".s_mi").addClass("mainIn");
			if($(top.window).height() - 215 > bts){
	    		$(".bank_test").height($(top.window).height() - 192);
	    	}
	    	$(top.window).resize(function(){
	    		if($(top.window).height() - 215 > bts){
	        		$(".bank_test").height($(top.window).height() - 192);
	        	}
	    	});
		}else{
			$("body").addClass("s_two s_leftmain");
	    	$(".bank_cont").addClass("s_maincont_wrap");
	    	$(".mainIn").css({"max-width": "100%"});
	    	$("div.work_cont").css("padding", "0 20px 30px 20px");	// 第一、二套模板  课件中  作业内容页面左右内边距设置
	    	
	    	if($(top.window).height() - 260 > bts){
	    		$(".bank_test").height($(top.window).height() - 260);
	    	}
	    	$(top.window).resize(function(){
	    		if($(top.window).height() - 260 > bts){
	        		$(".bank_test").height($(top.window).height() - 260);
	        	}
	    	});
		}
	}
	if(tempateType == 8){
        var  height = $(window).height();
        $(".mainIn").css("min-height",height + "px");
	}
});

//返回自测列表
function backTestList() {
	var courseId = $("#current_courseId").val();
	var itemId = $("#current_itemId").val();
	var columnTypeId = getColumnTypeId();
	window.location.href=basePath+'/course/test/coursewareTest_intoCourseTestListStudent.action?params.itemId='+itemId+'&params.courseId='+courseId+'&params.flag=1&params.columnTypeId='+columnTypeId;
}

// 获取自测的节点栏目类型
function getColumnTypeId() {
	var columnTypeId = "";
	var courseId = $("#current_courseId").val();
	var testId = $("#current_testId").val();
	$.ajax({
		url: basePath+'/course/test/coursewareTest_getItemColumnTypeId.action',
		type: 'post',
		data: {"courseId":courseId, "testId": testId},
		dataType: 'json',
		cache: false,
		async: false,
		success: function(result){
			if(result && result.status == "0") {
				columnTypeId = result.data.columnTypeId;						
			}
		},
		error: function(){alert(i18nMsg('test_page.test_page_operation.failLoadColumn'));}
	});
	return columnTypeId;
}

//===============================获取 学生答题信息  start========================================
// 获取多选题的答案
function transferToAnswerFromArray(array) {
	var result = "";

	if (array != null && array.length > 0) {
		for ( var i = 0; i < array.length; i++) {
			if (array[i].checked == true) {
				result += array[i].value;
			}
		}
	}
	if(result == "") {
		result = "NULL";
	}
	return result;
}

//对问题的答案处理,转换成答案字符串
function dealUserAnswerToStr() {
    //整个试卷的答案字符串
	var myAnswerStr = "";
	var allQuestionNum = document.getElementById("current_allNum").value;
	if(allQuestionNum != undefined && allQuestionNum != null){
	    for ( var i = 0; i < allQuestionNum; i++) {
	        var currentQuestionInputArray = document.getElementsByName("questionInput_" + i);
	        // 获取学生该题的答案
	        var myCurrentQuestion = transferToAnswerFromArray(currentQuestionInputArray);
	        
	        if(i == 0){
	            myAnswerStr += myCurrentQuestion;
	        }else{
	            myAnswerStr += ("|"+myCurrentQuestion);
	        }
	    }
	}
	return myAnswerStr;
}

/**
 * 检测字符串是否不为空
 * @param str 待检测的字符串
 * @return true: 不为空；false: 为空（null、""、"undefined"）
 */
function isNotEmpty(str){

	var isPass = false;
	if(str != null && str != "" && str != "undefined") {
		isPass = true;
	}
	return isPass;
}

/**
 * 检测字符串是否为空
 * @param str 待检测的字符串
 * @return true: 为空（null、""、"undefined","NULL"）；false: 不为空
 */
function isEmpty(str){

	var isPass = false;
	if(str == null || str == ''|| str == 'NULL' || str == "undefined"){
		isPass = true;
	}
	return isPass;
}

//对未做的问题的答案进行检测
function checkAnswerNodo() {
	var result = true;
	var allQuestionNum = document.getElementById("current_allNum").value;
	
	for ( var i = 0; i < allQuestionNum; i++) {
		var currentQuestionInputArray = document.getElementsByName("questionInput_" + i);
		// 获取学生该题的答案
		var myCurrentQuestion = transferToAnswerFromArray(currentQuestionInputArray);
		
		if(isEmpty(myCurrentQuestion)){
			$("span[name='tipNodo_"+i+"']").show();
			result =  false;
		}else{
			$("span[name='tipNodo_"+i+"']").hide();
		}
	}
	return result;
}


// 获取用户的试卷答案
function getMyAnswer() {
	// 获取testId itemId
	var testId = $("#current_testId").val();
	var itemId = $("#current_itemId").val();
	var historyId = $("#current_historyId").val();

	// 对问题的答案处理,转换成答案字符串
	var userAnswers = dealUserAnswerToStr();

	var myAnswer = {
		"testId" : testId,
		"itemId" : itemId,
		"historyId" : historyId,
		"myAnswers": userAnswers
	};
	return myAnswer;
}

//===============================获取 学生答题信息  end========================================




//===============================学生提交试卷  start========================================

function handSubmitNoResult(){
 // 获取答卷信息
    var myAnswer = getMyAnswer();
    var showResultUrl = "";
    // ajax 请求
    $.ajax({
        url: basePath + '/course/test/coursewareTest_handSubmitPaper.action',
        data: {
            "testId": myAnswer.testId,
            "itemId": myAnswer.itemId,
            "historyId": myAnswer.historyId,
            "myAnswers": myAnswer.myAnswers
        }, 
        type: 'post',
        cache: false,
        async: false,
        success: function(data){
        	if(data.success) {
                var itemId = $("#current_itemId").val();
                showResultUrl = basePath + '/course/test/coursewareTest_intoTestPage.action?params.itemId='+itemId;
            } else{
                alert(i18nMsg('test_page.test_page_operation.failOperate'));
            }
        },
        error:function(){
            alert(i18nMsg('test_page.test_page_operation.failSendRequest'));
        }
    });
    
    return showResultUrl ;
}

/**
 * 手动提交试卷
 */
function handSubmit(isCheckFlag) {
	var kjmark = $('#current_flag').val();
	//如果需要检验是否有题目未做
	if(isCheckFlag){
		var result = checkAnswerNodo();
		if(!result){
			if(!confirm(i18nMsg('test_page.test_page_operation.unFinishYet'))){
				return ;
			}
		}
	}

	if (!ishandsubmit) {
		// 获取答卷信息
		var myAnswer = getMyAnswer();
		ishandsubmit = true;
		var costTimes = $("#startTime").val();

		var form = $("<form></form>");
        form.attr('action',basePath + '/course/test/coursewareTest_handSubmitPaperToResult.action?flag=' + kjmark);
        form.attr('method','post');
        var testIdInput=$("<input type='text' name='testId'/>");
        testIdInput.attr("value", myAnswer.testId);
        var itemIdInput=$("<input type='text' name='itemId'/>");
        itemIdInput.attr("value", myAnswer.itemId);
        var historyIdInput=$("<input type='text' name='historyId'/>");
        historyIdInput.attr("value", myAnswer.historyId);
        var myAnswersInput=$("<input type='text' name='myAnswers'/>");
        myAnswersInput.attr("value", myAnswer.myAnswers);
        var costTimesInput=$("<input type='text' name='costTimes'/>");
        costTimesInput.attr("value", costTimes);
        form.append(testIdInput);
        form.append(itemIdInput);
        form.append(historyIdInput);
        form.append(myAnswersInput);
        form.append(costTimesInput);
        form.appendTo("body");
        form.css('display','none');
        form.submit();


		// ajax 请求
		// $.ajax({
		// 	url: basePath + '/course/test/coursewareTest_handSubmitPaper.action',
		// 	data: {
		// 		"testId": myAnswer.testId,
		// 		"itemId": myAnswer.itemId,
		// 		"historyId": myAnswer.historyId,
		// 		"myAnswers": myAnswer.myAnswers,
		// 		"costTimes": costTimes
		// 	},
		// 	type: 'post',
		// 	cache: false,
		// 	async: false,
		// 	success: function(data){
		// 		if(data.success) {
		// 			//显示测试成绩
		// 			var itemId = $("#current_itemId").val();
		// 			var showResultUrl = basePath + '/course/test/coursewareTest_intoTestPage.action?params.itemId='+itemId;
		// 			ishandsubmit = true;
		// 			window.location.href = showResultUrl;
		// 		} else{
		// 			ishandsubmit = false;
		// 			alert("操作失败！");
		// 		}
		// 	},
		// 	error:function(XMLHttpRequest, textStatus, errorThrown){
		// 		ishandsubmit = false;
		// 	    alert("发送请求失败,如有需要请联系管理员！");
		// 	}
		// });
	}
}


/**
 * 自动提交试卷
 */
function autoSubmit() {
	
	// 获取答卷信息
	var myAnswer = getMyAnswer();
    var costTimes = $("#costTime").val();
	// ajax 请求
	$.ajax({
		url: basePath + '/course/test/coursewareTest_autoSubmitPaper.action',
		data: {
			"testId": myAnswer.testId,
			"itemId": myAnswer.itemId,
			"historyId": myAnswer.historyId,
			"myAnswers": myAnswer.myAnswers,
            "costTimes": costTimes
		}, 
		type: 'post',
		cache: false,
		async: false,
		success: function(data){
			if(data.result != 'success'){
//				alert("自动提交试卷失败!");
			}
		},
		error:function(XMLHttpRequest, textStatus, errorThrown){
		    alert(i18nMsg('test_page.test_page_operation.touchAdmin'));
		    console.error(errorThrown);
		}
	});
}

//重做试卷
function redoTestPaper(){
	// 获取 itemId  courseId  historyId
	var itemId = $("#current_itemId").val();
	var courseId = $("#current_courseId").val();
	var historyId = $("#current_historyId").val();
	
	var url = basePath + '/course/test/coursewareTest_intoRedoTestPage.action?params.itemId='+itemId+'&params.courseId='+courseId+'&params.historyId='+historyId;
	window.location.href=url;
}

//查看答案
function sureScoreAndQueryAnswer(){
	var itemId = $("#current_itemId").val();
//	var url = basePath + '/course/test/coursewareTest_intoTestAnswerPage.action?itemId='+itemId;
	var currentFlag = $("#current_flag").val();
	var courseId = $("#current_courseId").val();
	var title = $("#current_title").val();
	var content = "查看：" + title + "答案";
	var url = basePath + '/course/test/coursewareTest_intoTestAnswerPage.action?itemId='+itemId + "&params.courseId=" + courseId;

	if("true" == currentFlag){
		url += '&flag=true';
	}

	$.ajax({
		url: CommonUtil.getPlatformPath() + '/learn/operateLog/saveOperateLog.json',
		type: 'post',
		data: {"params.courseId": courseId, "params.itemId": itemId, "params.operateContent": content, "params.operateCategory": "test", "params.operateType": "check_test_answers"},
		dataType: 'json',
		async: false,
		cache: false,
	});
	window.location.href=url;
}
//===============================学生提交试卷  end========================================


//===============================倒计时  start========================================
//给出的分钟数
var alltime = $("#zongshijian").val();

function setEndTimeLong(){
	 var now = new Date().getTime();
	 var giventime = alltime*60*1000;
	 var endtime = now + giventime;

	 $("#startTime").val(now);
	 $("#endTime").val(endtime);
}

//获取剩余的时间
function getRemainTimeLong(){
	 var endtime = $("#endTime").val();
	 var now = new Date().getTime();
	 return (endtime - now);
}

function autoCompleteToTwoChar(num){
	 
	 if(num < 10){
		 return "0"+num;
	 }else{
		 return num;
	 }
}

function formatToTimeString(remainTimeLong){
	 var seconds = remainTimeLong/1000;
	 seconds = Math.round(seconds);
	 
	 var ss = (seconds%3600)%60;//秒数 3600 + 120 +3 1：02：03  
	 var mm = Math.floor((seconds - ss)%3600/60);
	 var hh = (seconds - (seconds%3600))/3600;
	 
    ss = autoCompleteToTwoChar(ss);
    mm = autoCompleteToTwoChar(mm);
    hh = autoCompleteToTwoChar(hh);
    
    return hh+":"+mm+":"+ss;	 
}

function getcTime(){
	 
	 //获取剩余时间
	 var remainTimeLong = getRemainTimeLong();
	 if(remainTimeLong<=0){
		 //倒计时结束，则自动提交试卷
		 handSubmit(false);
	 }else{
		 var remainTimeString = formatToTimeString(remainTimeLong);
		 $("#daojishi").html(remainTimeString);
	 }
}


//判断是否有倒计时，如果有，则进行倒计时
var clockFlag = $("#clockFlag").val();
if(clockFlag == '1'){
	//设置到点时间
	setEndTimeLong();
	setInterval('getcTime()',1000);	
}

//===============================倒计时  end========================================

//===============================确定查看答案弹出框 start========================================

//确认答案
function sureAnswerDialog(_this){
	//var msg = "确定成绩查看答案后，您将不能再次重做，是否要确定成绩";
	//showSmallConfirmBox(_this, msg, sureScoreAndQueryAnswer);
    $.messager({
        content: i18nMsg('test_page.test_page_operation.seeAnswer'),
        messagerType: "info",
        okCallBack: function () {
            sureScoreAndQueryAnswer();
        }
    });
    return false;
}

//显示小确认框
function showSmallConfirmBox(_this, msgContent, afterConfirm){

	 //对弹出框的内容进行设置
	 $("#sureAnswerTool .small_cont").text(msgContent);
	 $("#sureAnswerTool").css("display", "block");
	 
	 var positions = $(_this).offset();
	 $("#sureAnswerTool").show().offset({top: positions.top - 110,left: positions.left - 25});//弹出框定位
	 
	 $("#sureAnswerTool").off("click", "#small_submit_comfirm_sureAnswerTool"); 
	 $("#sureAnswerTool").on("click", "#small_submit_comfirm_sureAnswerTool", function(){
	       
		 $("#sureAnswerTool").css("display", "none");
		 afterConfirm();
	 });
}

//取消时，隐藏确认框
function hideByDivId(divId){
	$("#"+divId).hide();
}

function showConfirmExit(){
/*	$("#testExitConfirm", top.window.document).off("click", ".popConfirm"); 
	$("#testExitConfirm", top.window.document).on("click",".popConfirm",function(){
		$("#confirmTool", top.window.document).dialog("close");
		handSubmit(false);
	});
	$("#testExitConfirm", top.window.document).off("click", ".popCancel"); 
	$("#testExitConfirm", top.window.document).on("click",".popCancel",function(){
		$("#testExitConfirm", top.window.document).dialog("close");
	});*/
}


function onKeyDown(){
	if ((event.keyCode==116)||(window.event.ctrlKey)||(window.event.shiftKey)||(event.keyCode==122)){
		event.keyCode=0;
		event.returnValue=false;
	}
}

function altKeyDown(){
	if(window.event.altKey){
		window.event.returnValue=false;
	}
}
document.onkeydown = altKeyDown;
