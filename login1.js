var _LOGINTYPE;
var _LOGINID_;
var _TRUENAME_;
var _PHOTO_;
var isRegisterShow = true;
var CENTERURL = '';
var JUMPURL = '';
var IsOpenManagerWeChatCheck = false;
var learnCenterIndex = '/u/student/study/myCourse.action';
// 验证码登录自动注册获取验证码
var canAutoRes = false;
// 微信登录自动注册获取验证码
var wxBindPhoneFlag = false;
//是否开启公众号绑定
var isOpenLinkWechat = false;
function getRegisterConfig() {
    var url = location.search; // 获取url中"?"符后的字串
    portal = url.replace("?portal=", "")
    let portalPath = $.cookies.get("portalPath");
    if (portalPath != portal) {
        portal = portalPath
    }
    let registerSettingConfig = getPortalConfig("registerSettingConfig",portal);
    if (registerSettingConfig) {
        let typeList = registerSettingConfig[0];
        let extraInfo = eval('(' + typeList.extraInfo + ')');
        // 0 关闭 1 开启 2 第三方注册
        isRegisterShow = extraInfo.openRegisterWay;
        canAutoRes = extraInfo.verifiCodeLoginAutoRegis;
        wxBindPhoneFlag = extraInfo.wxLoginAutoRegis;
        if (!isRegisterShow || '0' == isRegisterShow ) {
            // 隐藏注册
            $(".headerRegister").hide();
            $("#loginResiger").hide();
            $("#loginResiger2").hide();
            $("#portalResiger").hide();
            $("#portalResiger2").hide();
            $("#register").hide();
            $("#registerNew").hide();
        } else {
            // 显示注册
            $(".headerRegister").show();
            $("#loginResiger").show();
            $("#loginResiger2").show();
            $("#portalResiger").show();
            $("#portalResiger2").show();
            $("#register").show();
            $("#registerNew").show();

            if('2' == isRegisterShow){
                $("#portalResiger").click(function (event) {
                    event.preventDefault();
                    parent.oepnThirdPop(typeList.isRegister)

                })
                $("#portalResiger2").click(function (event) {
                    event.preventDefault();
                    parent.oepnThirdPop(typeList.isRegister)

                })
                $(".headerRegister").click(function (event) {
                    event.preventDefault();
                    parent.oepnThirdPop(typeList.isRegister)
                })
            }
        }
    } else {
        registerSettingConfig = getSiteConfig("registerSettingConfig");
        // 如果2.11新功能没有那么还是走之前的配置
        if (registerSettingConfig) {
            var typeList = registerSettingConfig[0];
            var extraInfo = eval('(' + typeList.extraInfo + ')');
            // 0 关闭 1 开启 2 第三方注册
            isRegisterShow = extraInfo.openRegisterWay;
            canAutoRes = extraInfo.verifiCodeLoginAutoRegis;
            wxBindPhoneFlag = extraInfo.wxLoginAutoRegis;
            if (!isRegisterShow || '0' == isRegisterShow ) {
                // 隐藏注册
                $(".headerRegister").hide();
                $("#loginResiger").hide();
                $("#loginResiger2").hide();
                $("#portalResiger").hide();
                $("#portalResiger2").hide();
                $("#register").hide();
                $("#registerNew").hide();
            } else {
                // 显示注册
                $(".headerRegister").show();
                $("#loginResiger").show();
                $("#loginResiger2").show();
                $("#portalResiger").show();
                $("#portalResiger2").show();
                $("#register").show();
                $("#registerNew").show();
                if('2' == isRegisterShow){
                    $("#portalResiger").click(function (event) {
                        event.preventDefault();
                        parent.oepnThirdPop(typeList.isRegister)

                    })
                    $("#portalResiger2").click(function (event) {
                        event.preventDefault();
                        parent.oepnThirdPop(typeList.isRegister)

                    })
                    $(".headerRegister").click(function (event) {
                        event.preventDefault();
                        parent.oepnThirdPop(typeList.isRegister)
                    })
                }
            }
        }
    }
}

function getWeChatConfig() {
    let siteConfig = getSiteConfig("isOpenLinkWechat");
    if(siteConfig && siteConfig[0].configContent == '开启') {
        isOpenLinkWechat = true;
    }
}


//回车提交事件
$("body").keydown(function () {
    if (event.keyCode == "13") {//keyCode=13是回车键
        doSubmit();
    }
});
//--------回车提交事件完毕---------------------//

// 获取个人中心左侧菜单配置
function getLearningCenterSetting() {
    var paramsData = {
        params: {
            organId: $.cookies.get("organId")
        }
    }
    $.ajax({
        url: "/api/learning/center/setting/list",
        type: 'POST',
        dataType: 'json',
        async: false,
        contentType: 'application/json;charset=utf-8',
        data: JSON.stringify(paramsData),
        success: function (data) {
            if (data.data && data.data.length > 0) {
                for (var i = 0; i < data.data.length; i++) {
                    for (var j = 0; j < data.data[i].learnCenterSettingChildren.length; j++) {
                        if (data.data[i].learnCenterSettingChildren[j].isShow) {
                            CENTERURL = data.data[i].learnCenterSettingChildren[j].redirectUrl;
                            $.cookies.set("centerurl", CENTERURL);
                            window.parent.location.href = data.data[i].learnCenterSettingChildren[j].redirectUrl;
                            return;
                        }
                    }
                }
            }
        },
        error: function () {
            //layer.alert("请求失败！");
        }

    });
}

//退出
function _logout() {
    $.cookies.del(_LOGINID_ + "popUp");
    $.cookies.del("isSyncElectiveToLearning");

    // 业务系统退出逻辑
    function doBusinessLogout() {
        if (_LOGINTYPE == '3') {
            $.ajax({
                type: "post",
                cache: false,
                async: false,
                url: "/api/logout",
                dataType: "json",
                success: function (data) {
                    window.parent.location.href = "/sso/ssoLogin_logout.action";
                },
                error: function () {
                    window.parent.location.href = "/sso/ssoLogin_logout.action";
                }
            });
        } else {
            window.parent.location.href = "/sso/ssoLogin_logout.action";
        }
    }

    // 判断是否配置了用户中心
    if (typeof uc_base_path !== 'undefined' && uc_base_path) {
        // 有配置，先调用用户中心退出
        $.ajax({
            url: uc_base_path + '/logout',
            xhrFields: {withCredentials: true}
        }).always(doBusinessLogout);
    } else {
        // 没配置，直接走业务系统退出
        doBusinessLogout();
    }
}

//进入个人中心
function _join() {
    if (_LOGINTYPE == '3') {
        window.parent.location.href = "/controller/#/entrance";
    } else if (_LOGINTYPE == '1') {
        window.parent.location.href = "/u/teacher/teaching/index.action";
    } else {
        if($.cookies.get("aigc")){
            window.parent.location.href = getAICenterUrl();
            return ;
        }
        let portalConfig = getPortalConfig("AIConfigs","");
        if (portalConfig) {
            let typeList = portalConfig[0];
            let extraInfo = eval('(' + typeList.extraInfo + ')');
            if(extraInfo.openLearnRobot && extraInfo.aiRadio == '2'){
                window.parent.location.href = getAICenterUrl();
                return ;
            }
        }
        learnCenterIndex = $.cookies.get("learnCenterIndex");
        var queryTheme = $.cookies.get("theme");
        if(learnCenterIndex&&queryTheme&&(queryTheme=='redA'||queryTheme=='green'||queryTheme=='blue')){
            learnCenterIndex = learnCenterIndex.replace(".action","Theme.action")
        }
        window.parent.location.href = learnCenterIndex;
    }

}

function getAICenterUrl(){
    return "/u/student/training/aigc.action";
}

//进入我的订单
function toMyOrder() {
    window.open("/u/student/training/myorder.action");
}

// 进入我的购物车
function toMyCart() {
    window.open("/u/student/settlement/cartlist.action");
}

// 进入修改资料
function toUserInfo() {
    window.open("/u/student/modify/user.action");
}

// 进入账号安全
function toUserSecurity() {
    window.open("/u/student/account/security.action");
}

function ucIsLogin(){
    if(uc_login){
        return ;
    }
    getMangeCfgChangeDate();
    if(!uc_base_path || uc_base_path === ''){
        return ;
    }
    $.ajax({
        type: "post",
        async: false,// 同步
        url: uc_base_path + "/open/api/checkLogin",
        xhrFields: {withCredentials: true},
        success: function (res) {
            if (res.success && res.message) {
                const uCenterToken = res.message
                if(uCenterToken){
                    $.ajax({
                        type: "post",
                        async: false,// 同步
                        url: "/center/user/loginByUCenter.do",
                        data:{"ucenterToken":uCenterToken,"client_id":uc_client_id,"siteCode":_SITECODE_,"siteType":"typx"},
                        xhrFields: {withCredentials: true},
                        success: function (res) {
                             if (res) {
                                 const result = JSON.parse(res);
                                 if(result.result === "success"){
                                     uc_login = true;
                                     getMangeCfgChangeDate(true);
                                 }
                             }
                        }
                    });
                }
            }
        }
    });
}

// 验证是否登录
function validateUser(interval) {
	if($.cookies.get("preview_portal")) return false;
	if(!interval){
        ucIsLogin();
    }
    var data = {};
    data["auto"] = false;
    data["info"] = 1;
    var flag = false;
    $.ajax({
        data: data,
        type: "post",
        cache: false,
        async: false,// 同步
        url: "/sso/ssoLogin_info.action",
        dataType: "jsonp",
        jsonp: "jsoncallback",
		xhrFields: {withCredentials: true},
        success: function (res) {
            var data = res.data;
            if (data.status === "success") {
                _LOGINID_ = data.loginId;
                _TRUENAME_ = data.trueName;
                _LOGINTYPE = data.type;
                _PHOTO_ = data.photo;
                flag = true;
            } else {
                flag = false;
            }
        }
    });
    if (flag && _LOGINTYPE != '0') {
        $.ajax({
            type: "post",
            cache: false,
            async: false,// 同步
            url: "/api/learning/userInfo/isLogin",
            dataType: "json",
            success: function (res) {
            },
            error: function (xmlHttpRequest, textStatus, errorThrown) {
                if (xmlHttpRequest.status === 401) {
                    flag = false;
                    var responseJson = JSON.parse(xmlHttpRequest.responseText);
                    if (responseJson.error === 'single_login') {
                        layer.alert("账号已在其他设备登录，您当前账号已退出，如不是本人操作，请立即找回密码或反馈管理员重置密码。");
						_logout()
                    }
                }
            }
        });
    }
    return flag;
}

var validateUserInterval;

function enableValidateUserInterval(enable) {
    login = enable;
    if (enable && !validateUserInterval) {
        validateUserInterval = setInterval(function () {
            enableValidateUserInterval(validateUser(true))
        }, 10 * 1000);
    }
    if (!enable && validateUserInterval) {
        clearInterval(validateUserInterval)
    }
}

function reloadcode() {
    var verify = document.getElementById('img_data');
    verify.setAttribute('src', '/center/sso/authimg?' + Math.random());
}

function GetRequest() {
    var url = location.search; // 获取url中"?"符后的字串
    url = url.replace("?toBackURL=", "")
    return url;
}

function doSubmit() {
    $('#mt8_yzm').hide()
    var name = $("#user1").val();
    if (name == "" || name == "邮箱/手机号") {
        $('#mt8_user').show()
        $("#user1").focus();
        return;
    }
    $('#mt8_user').hide()
    var password = $("#pwd1").val();
    if (password == "" || password == "密码") {
        $('#mt8_pwd').show()
        $("#pwd1").focus();
        return;
    }
    $('#mt8_pwd').hide()
    var falseNum = $.cookies.get("falseNum");
    if (null != falseNum && falseNum >= 3) {
        var authCode = $("#authCode").val();
        if (authCode == "" || authCode == "验证码") {
            $('#mt8_yzm').show()
            $("#authCode").focus();
            return;
        }
        $('#mt8_yzm').hide()
    }
    var pwd = password;
    // password = MD5($.trim(password).replace(/\%/g, "%25").replace(/\+/g, "%2B").replace(/\&/g, "%26"));
    password = password.replace("。", ".");
    password = MD5($.trim(password));
    /*password= MD5(password+"0c42a1647Ccc");*/
    /********************login start*********************/
    loginCenter({
        loginId: name,
        password: password,
        authCode: authCode
    });
    /*******************login end**********************/
}


function portalDoSubmit(portal) {
    var name = $("#user1").val();
    name = name.trim();
    if (name == "" || name == "请输入用户名/手机号") {
        showMsg("","用户名不能为空");
        return;
    }
    var password = $("#pwd1").val();
    password = password.trim();
    if (password == "" || password == "密码") {
        showMsg("","密码不能为空");
        return;
    }
    var falseNum = $.cookies.get("falseNum");
    if (null != falseNum && falseNum >= 3) {
        var authCode = $("#authCode").val();
        if (authCode == "" || authCode == "验证码") {
            showMsg("","验证码不能为空");
            return;
        }
    }
    var pwd = password;
    // password = MD5($.trim(password).replace(/\%/g, "%25").replace(/\+/g, "%2B").replace(/\&/g, "%26"));
    password = password.replace("。", ".");
    password = MD5($.trim(password));
    /*password= MD5(password+"0c42a1647Ccc");*/
    /********************login start*********************/
    var data = {
        loginId: name,
        password: password,
        authCode: authCode,
   
        portal: portal
    }
    $.cookies.set("chooseRoleData",data)
    loginCenter(data);
    /*******************login end**********************/
}
function portalDoSubmitNew(portal) {
    var name = $("#user1").val();
    name = name.trim();
    if (name == "" || name == "请输入用户名/手机号") {
        showMsg("","用户名不能为空");
        return;
    }
    var password = $("#pwd1").val();
    password = password.trim();
    if (password == "" || password == "密码") {
        showMsg("","密码不能为空");
        return;
    }
    var falseNum = $.cookies.get("falseNum");
    if (null != falseNum && falseNum >= 3) {
        var authCode = $("#authCode").val();
        if (authCode == "" || authCode == "验证码") {
            showMsg("","验证码不能为空");
            return;
        }
    }
    var pwd = password;
    // password = MD5($.trim(password).replace(/\%/g, "%25").replace(/\+/g, "%2B").replace(/\&/g, "%26"));
    password = password.replace("。", ".");
    password = MD5($.trim(password));
    /*password= MD5(password+"0c42a1647Ccc");*/
    var bindUnionid = $.cookies.get("bindUnionid");
    /********************login start*********************/
    var data = {
        loginId: name,
        password: password,
        authCode: authCode,

        portal: portal,
        unionId:bindUnionid,
        loginModuleTypeByWxLogin:"5"
    }
    $.cookies.set("chooseRoleData",data)
    loginCenter(data);
    /*******************login end**********************/
}


function showMsg(tig, msg) {
    if(msg.length>15){
        layer.msg(msg ,{  shade:0,  time: 2000, offset: (window.innerHeight / 2 -20) + 'px',area: [,'80px' ]}, function(){});
    }else{
        layer.msg(msg ,{  shade:0,  time: 2000, offset: (window.innerHeight / 2 -20) + 'px',area: [,'50px' ]}, function(){});
    }
}

function showMsgNew(tig, msg) {
    layer.msg(msg ,{  shade:0,  time: 2000, offset: ['40%','30%']}, function(){});
}

function loginCenter(data) {
    var siteCode = $("#siteCode").val();
    var loginModule = "0";
    if(data.loginModule && data.loginModule !=""){
        loginModule = data.loginModule;
    }
    //getLearningCenterSetting();
    var toBackURL = GetRequest();
    if (!learnCenterIndex) {
        learnCenterIndex = $.cookies.get("learnCenterIndex");
    }
    if (data.portal != "" && data.portal != null) {
        if (learnCenterIndex && learnCenterIndex != "") {
            toBackURL = learnCenterIndex;
        } else {
            toBackURL = "/u/student/study/myCourse.action";
        }
    }
    var queryTheme = $.cookies.get("theme");
    if(toBackURL&&queryTheme&&(queryTheme=='redA'||queryTheme=='green'||queryTheme=='blue')){
        toBackURL = toBackURL.replace(".action","Theme.action")
    }
    var param = {
        auto: false,
        info: 1,
        siteCode: siteCode,
        siteType: "typx",
        ip: 1,
        json: "json",
        allRole: "allRole"
    };
    for (var prop in data) {
        if (Object.prototype.hasOwnProperty.call(data, prop)) {
            param[prop] = data[prop]
        }
    }
    var flagPhoneLogin = data.flagPhoneLogin;
    var checkStatus = '0'
    // if(flagPhoneLogin && flagPhoneLogin ==='1'){
    //     checkStatus = '0';
    // }else {
    //     checkStatus = checkPassWordNew(data.loginId, data.pwd);
    // }
    // 校验密码是否符合规范
    $.ajax({
        data: param,
        type: "post",
        dataType: "json",
        url: "/center/user/login.do",
        success: function (data) {
			if(!$.cookies.get("siteCode")){
				$.cookies.set("siteCode", siteCode, {path: '/'});
			}
            var flagIsStudent = data.flagIsStudent
            var flagIsBindWeChat = data.flagIsBindWeChat
            var flagIsNeedBindWeChatRole = data.flagIsNeedBindWeChatRole
            var role = data.role
            var unionId = ""
            if(data.unionId!=undefined&&data.unionId!=null&&data.unionId!=''){
                unionId = data.unionId;
            }
            if(''!=role&&'null'!=role&&null!=role&&'undefined'!=role&&undefined!=role){
                role = returnRole(role)
            }
            if(data.code == "200" && data.chooseRole == '1'){
                showRoleLogin(data)
            }else if (data.code == "200") {
				$.cookies.set("chooseRoleData",{})
                if ($("#checkbox-1").is(":checked")) {//记住密码是否被选中
                    //记住密码被选中,向cookie中存入用户名和密码
                    $.cookies.set("username", param.loginId, {hoursToLive: 24 * 30, domain: "webtrn.cn", path: '/'});
                    $.cookies.set("password", param.pwd, {hoursToLive: 24 * 30, domain: "webtrn.cn", path: '/'});
					localStorage.setItem('rememberCurrentLoginId',param.loginId);
                } else {
                    //否则只记住用户名
                    $.cookies.set("username", param.loginId, {hoursToLive: 24 * 30, domain: "webtrn.cn", path: '/'});
                    $.cookies.set("password", "", {hoursToLive: 24 * 30, domain: "webtrn.cn", path: '/'});
					localStorage.setItem('rememberCurrentLoginId',param.loginId);
                }
                var bindResult = bindUser({
                    loginId: param.loginId,
                    password: param.password
                })

                //如果开启了微信公众号扫码登录
                if(isOpenLinkWechat){
                    // 当前为学员的话 就走新判断密码强度逻辑
                    if(flagIsStudent){
                        var bindResultWx = bindUserWx({
                            loginId: param.loginId,
                            password: param.password
                        })
                        if (bindResultWx) {
                            var login = false;
                            if (bindResultWx === '当前账号已经进行过绑定，请检查账号或者联系管理员') {
                                parent.layer.confirm(bindResultWx, {
                                    btn: ['重新输入']
                                }, function (index) {
                                    parent.layer.close(index)
                                }, function (index) {
                                    parent.layer.close(index)
                                });
                            } else {
                                parent.layer.alert(bindResultWx);
                            }
                            return;
                        }
                    }else {

                        // 当前角色为管理员和班主任 并且需要强制绑定验证微信
                        if (IsOpenManagerWeChatCheck && flagIsNeedBindWeChatRole) {
                            if (bindResult) {
                                var login = false;
                                if (bindResult === '当前账号已经进行过绑定，请检查账号或者联系管理员') {
                                    parent.layer.confirm(bindResult, {
                                        btn: ['直接登录', '重新输入']
                                    }, function (index) {
                                        parent.layer.close(index)
                                        if (typeof data.is_mg == "undefined") {
                                            if (toBackURL == '' || toBackURL == null) {
                                                toBackURL = "/cms";
                                            }
                                            JUMPURL = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        } else {
                                            JUMPURL = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        }
                                    }, function (index) {
                                        parent.layer.close(index)
                                    });
                                } else {
                                    parent.layer.alert(bindResult);
                                }
                            } else {
                                if (typeof data.is_mg == "undefined" || data.is_mg == false) {
                                    if (toBackURL == '' || toBackURL == null) {
                                        toBackURL = "/cms";
                                    }
                                    JUMPURL = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&portal=_" + $.cookies.get('portalPath') + "&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                } else {
                                    JUMPURL = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                }
                            }
                            showBindWeChatCode(flagIsBindWeChat, param.loginId, JUMPURL);
                            return;
                            // // 没有绑定
                            // if(flagIsBindWeChat === null || flagIsBindWeChat ==='' || flagIsBindWeChat ===undefined || flagIsBindWeChat ==='undefined' || flagIsBindWeChat ==='null'){
                            //     // $("#managerCodeId").show()
                            //
                            // }else {
                            //     window.top.location.href = JUMPURL;
                            // }
                        } else {
                            // 当前角色为讲师 走正常的逻辑
                            if (bindResult) {
                                var login = false;
                                if (bindResult === '当前账号已经进行过绑定，请检查账号或者联系管理员') {
                                    parent.layer.confirm(bindResult, {
                                        btn: ['直接登录', '重新输入']
                                    }, function (index) {
                                        parent.layer.close(index)
                                        if (typeof data.is_mg == "undefined") {
                                            if (toBackURL == '' || toBackURL == null) {
                                                toBackURL = "/cms";
                                            }
                                            window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        } else {
                                            window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        }
                                    }, function (index) {
                                        parent.layer.close(index)
                                    });
                                } else {
                                    parent.layer.alert(bindResult);
                                }
                            } else {
                                if (typeof data.is_mg == "undefined" || data.is_mg == false) {
                                    if (toBackURL == '' || toBackURL == null) {
                                        toBackURL = "/cms";
                                    }
                                    //教师初始密码校验
                                    var paramData = {params: {loginId: param.loginId,siteCode: siteCode}}
                                    $.ajax({
                                        data: JSON.stringify(paramData),
                                        type: "post",
                                        contentType: 'application/json',
                                        dataType: "json",
                                        async:false,
                                        url: "/api/learning/userInfo/checkIfUseInitPassWord",
                                        success: function (resData) {
                                            if (resData.meta.errCode === 0) {
                                                if (resData.data.success) {
                                                    if (resData.data.flag === '0') {
                                                        // 需要修改密码
                                                        localStorage.setItem("isTeacherInitPassword","1");
                                                    }else{
                                                        localStorage.setItem("isTeacherInitPassword","0");
                                                    }

                                                }else{
                                                    localStorage.setItem("isTeacherInitPassword","0");
                                                }

                                            }else{
                                                localStorage.setItem("isTeacherInitPassword","0");
                                            }
                                        }
                                    })
                                    window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&portal=_" + $.cookies.get('portalPath') + "&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                    return;
                                } else {
                                    window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                    return;
                                }
                            }
                        }
                    }
                }


                    // 当前为学员的话 就走新判断密码强度逻辑
                    if (flagIsStudent) {
                        if (checkStatus === '0') {

                            if (bindResult) {
                                var login = false;
                                if (bindResult === '当前账号已经进行过绑定，请检查账号或者联系管理员') {
                                    parent.layer.confirm(bindResult, {
                                        btn: ['重新输入']
                                    }, function (index) {
                                        parent.layer.close(index)
                                        /* if (typeof data.is_mg == "undefined") {
                                             if (toBackURL == '' || toBackURL == null) {
                                                 toBackURL = "/cms";
                                             }
                                             window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                         } else {
                                             window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                         }*/
                                    }, function (index) {
                                        parent.layer.close(index)
                                    });
                                } else {
                                    parent.layer.alert(bindResult);
                                }
                            } else {
                                //绑定成功后清除cookie
                                $.cookies.del("openId");
                                $.cookies.del("unionIdByOpenId");
                                $.cookies.del("nickNameByOpenId");
                                if (typeof data.is_mg == "undefined"||data.is_mg==false) {
                                    if (toBackURL == '' || toBackURL == null) {
                                        toBackURL = "/cms";
                                    }
                                    if(isOpenLinkWechat){
                                        window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&portal=_"+$.cookies.get('portalPath')+"&ticket=" + data.tip.ticket + "&unionId=" + unionId + "&wechatFlag=1";
                                    }else {
                                        window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&portal=_"+$.cookies.get('portalPath')+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                    }
                                } else {
                                    if(isOpenLinkWechat){
                                        window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId + "&wechatFlag=1";
                                    }else {
                                        window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                    }
                                }
                            }

                        } else {
                            parent.layer.confirm('您的密码安全性较低，建议您更换安全性更高的密码', {
                                title: '温馨提示',
                                btn: ['修改密码'],
                                closeBtn: 0
                            }, function (index) {
                                parent.layer.close(index)
                                toBackURL = '/u/student/account/security.action?needUpdatePassword=1';
                                if(isOpenLinkWechat){
                                    window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&portal=_"+$.cookies.get('portalPath')+"&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId + "&wechatFlag=1";
                                }else {
                                    window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&portal=_"+$.cookies.get('portalPath')+"&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                }
                            });
                        }
                    } else {
                        // 当前角色为管理员和班主任 并且需要强制绑定验证微信
                        if (IsOpenManagerWeChatCheck && flagIsNeedBindWeChatRole) {
                            if (bindResult) {
                                var login = false;
                                if (bindResult === '当前账号已经进行过绑定，请检查账号或者联系管理员') {
                                    parent.layer.confirm(bindResult, {
                                        btn: ['直接登录', '重新输入']
                                    }, function (index) {
                                        parent.layer.close(index)
                                        if (typeof data.is_mg == "undefined") {
                                            if (toBackURL == '' || toBackURL == null) {
                                                toBackURL = "/cms";
                                            }
                                            JUMPURL = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        } else {
                                            JUMPURL = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        }
                                    }, function (index) {
                                        parent.layer.close(index)
                                    });
                                } else {
                                    parent.layer.alert(bindResult);
                                }
                            } else {
                                if (typeof data.is_mg == "undefined" || data.is_mg == false) {
                                    if (toBackURL == '' || toBackURL == null) {
                                        toBackURL = "/cms";
                                    }
                                    JUMPURL = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&portal=_" + $.cookies.get('portalPath') + "&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                } else {
                                    JUMPURL = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                }
                            }
                            showBindWeChatCode(flagIsBindWeChat, param.loginId, JUMPURL);
                            // // 没有绑定
                            // if(flagIsBindWeChat === null || flagIsBindWeChat ==='' || flagIsBindWeChat ===undefined || flagIsBindWeChat ==='undefined' || flagIsBindWeChat ==='null'){
                            //     // $("#managerCodeId").show()
                            //
                            // }else {
                            //     window.top.location.href = JUMPURL;
                            // }
                        } else {
                            // 当前角色为讲师 走正常的逻辑
                            if (bindResult) {
                                var login = false;
                                if (bindResult === '当前账号已经进行过绑定，请检查账号或者联系管理员') {
                                    parent.layer.confirm(bindResult, {
                                        btn: ['直接登录', '重新输入']
                                    }, function (index) {
                                        parent.layer.close(index)
                                        if (typeof data.is_mg == "undefined") {
                                            if (toBackURL == '' || toBackURL == null) {
                                                toBackURL = "/cms";
                                            }
                                            window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        } else {
                                            window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                        }
                                    }, function (index) {
                                        parent.layer.close(index)
                                    });
                                } else {
                                    parent.layer.alert(bindResult);
                                }
                            } else {
                                if (typeof data.is_mg == "undefined" || data.is_mg == false) {
                                    if (toBackURL == '' || toBackURL == null) {
                                        toBackURL = "/cms";
                                    }
                                    //教师初始密码校验
                                    var paramData = {params: {loginId: param.loginId,siteCode: siteCode}}
                                    $.ajax({
                                        data: JSON.stringify(paramData),
                                        type: "post",
                                        contentType: 'application/json',
                                        dataType: "json",
                                        async:false,
                                        url: "/api/learning/userInfo/checkIfUseInitPassWord",
                                        success: function (resData) {
                                            if (resData.meta.errCode === 0) {
                                                if (resData.data.success) {
                                                    if (resData.data.flag === '0') {
                                                        // 需要修改密码
                                                        localStorage.setItem("isTeacherInitPassword","1");
                                                    }else{
                                                        localStorage.setItem("isTeacherInitPassword","0");
                                                    }

                                                }else{
                                                    localStorage.setItem("isTeacherInitPassword","0");
                                                }

                                            }else{
                                                localStorage.setItem("isTeacherInitPassword","0");
                                            }
                                        }
                                    })
                                    window.top.location.href = "/sso/ssoLogin_centerLogin.action?toBackURL=" + escape(toBackURL) + "&loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&portal=_" + $.cookies.get('portalPath') + "&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                } else {
                                    window.top.location.href = "/sso/ssoLogin_centerLogin.action?loginId=" + param.loginId + "&passwd=" + param.password + "&auto=false&info=1&role="+role+"&ticket=" + data.tip.ticket + "&unionId=" + unionId;
                                }
                            }
                        }
                    }
                    //删除扫码后的信息
                    $.cookies.del("bindType");
                    $.cookies.del("bindCode");
                    $.cookies.del("bindUnionid");



            } else {
                //1代码短信登录，2代表微信，3代表app扫码，0代表账号密码，不同的module在不同的模块进行数据展示
                if('1' == loginModule){
                    showMsg('', data.tip)
                }else if("3" == loginModule){
                    showMsg('', data.tip)
                }else{
                    showMsg('', data.tip)
                }

                reloadcode();
                var falseNum = $.cookies.get("falseNum");
                if (!falseNum) {
                    $.cookies.set("falseNum", '1', {hoursToLive: 1});
                } else {
                    falseNum += 1;
                    $.cookies.set("falseNum", falseNum, {hoursToLive: 1});
                    if (falseNum >= 3) {
                        $("#authCodeDiv").css("display", "block");
                        $(".BanCon").css("margin-top", "0px");
                        $(".banV2-foot").css("bottom", "8px");
                    }
                }
            }
        }
    });
}

function getSiteCmsPathInfoQQQ() {
    let siteConfig = getSiteConfig("IsOpenManagerWeChatCheck");
    if(siteConfig && siteConfig[0].configContent == '开启') {
        // 强制修改密码关闭叉叉
        IsOpenManagerWeChatCheck = true;
    } else if (siteConfig && siteConfig[0].configContent == '关闭') {
        // 非强制限制叉叉
        IsOpenManagerWeChatCheck = false;
    }
}

/**
 * 管理员微信绑定
 * @param flagIsBindWeChat
 * @param loginId
 * @param JUMPURL
 */
function showBindWeChatCode(flagIsBindWeChat, loginId, JUMPURL) {
    var linkUrl = '//' + document.location.host + '/cms/res_base/typxNew/webtrn/article/css/iframe_login_wx.css';
    linkUrl = linkUrl.replace('http://', '//');
    linkUrl = linkUrl.replace('https://', '//');
    var toBackURL = "/cms";
    var title = "";
    var info = "";
    var webUrl = location.protocol + '//' + location.host + JUMPURL + '&userBind=';
    // 已经绑定过微信
    if (flagIsBindWeChat === null || flagIsBindWeChat === '' || flagIsBindWeChat === undefined || flagIsBindWeChat === 'undefined' || flagIsBindWeChat === 'null') {
        title = "管理员微信绑定";
        // 未绑定
        webUrl += 0;
        info = '<p style=" line-height: 20px;">请您用本人微信扫码绑定账号.为保证账号安全,<br/>后续登录时均需使用该微信扫码验证身份</p>';
    } else {
        title = "管理员微信验证";
        // 已绑定
        webUrl += 1;
        info = '<p style=" line-height: 20px;">为保证账号安全，请您使用此账号已绑<br/>定的微信扫码进行身份验证</p>';
    }

    var wechatCodeUrl = window.location.protocol+'//p.webtrn.cn/center/third/authRequst.do' +
        '?type=weixin&roleType=manager&terminal=web&errorDomain=' + encodeURIComponent(location.protocol + '//' + location.host) + '&service=' + encodeURIComponent(webUrl) + '&operateType=matchMangerWechat' +
        '&siteCode=' + _SITECODE_ + '&loginId=' + loginId + '&siteType=typx&toBackURL=' + escape(toBackURL) + '&href=' + encodeURIComponent(linkUrl);
    var wxcontent = '<div style="position: relative;margin-top:20px;margin-left: 20px;margin-right: 20px;text-align: center;"> '+info+'</div> <iframe src="'+wechatCodeUrl+'" frameborder="0" width="100%" height="200px"/>';
    parent.layer.open({
        type: 1,
        title: title,
        skin: 'wxqrcode',
        area: ['340px', '320px'],
        content: wxcontent,
        scrollbar:false
    })
}

function bindUser(param) {
    var bindType = $.cookies.get("bindType");
    var bindCode = $.cookies.get("bindCode");
    var bindUnionId = $.cookies.get("bindUnionid");
    var weChatNickName =  localStorage.getItem("nickNameForWxBind");
    if (!bindType || !bindCode) {
        return;
    }
    var result = '';
    param.bindType = bindType;
    param.bindCode = bindCode;
    param.bindUnionId = bindUnionId;
    param.noManager = 1;
    param.weChatNickName = weChatNickName;
    $.ajax({
        type: "POST",
        url: "/center/user/bindUser.do",
        data: param,
        dataType: "json",
        async: false,
        success: function (data) {
            if (data.result !== 'success') {
                result = data.tip;
            }
        }
    });
    if (!result) {
        $.cookies.del("bindType");
        $.cookies.del("bindCode");
        $.cookies.del("bindUnionid");
    }
    return result;
}


function bindUserWx(param) {
    var openId = $.cookies.get("openId");
    var unionIdByOpenId =  $.cookies.get("unionIdByOpenId");
    var nickNameByOpenId =  $.cookies.get("nickNameByOpenId");
    if (!openId) {
        return;
    }
    var result = '';
    param.openId = openId;
    param.noManager = 1;
    param.unionIdByOpenId = unionIdByOpenId;
    param.nickNameByOpenId = nickNameByOpenId;
    $.ajax({
        type: "POST",
        url: "/center/user/bindUserWx.do",
        data: param,
        dataType: "json",
        async: false,
        success: function (data) {
            if (data.result !== 'success') {
                result = data.tip;
            }
        }
    });
    return result;
}


function validPwdStrengthRtnString(pwd_ele) {
    var strength = "";
    //普通用户
    var user = validPwd(0, pwd_ele);
    if (user == 0 || user == 1 || user == 4 || user == 5 || user == 6) {
        //不通过  弱
        strength += 0;
    } else if (user == 2 || user == 7) {
        //通过  中
        strength += 1;
    } else if (user == 3) {
        //通过  强
        strength += 2;
    } else {
        strength += 0;
    }

    //超管
    var sup_admin = validPwd(1, pwd_ele);
    if (sup_admin == 9) {
        //通过
        strength += 1;
    } else {
        strength += 0;
    }
    return strength;
}

function validPwd(roleType, pwd_ele) {

    var pwdVal = pwd_ele;

    var result = 0;
    var minLength = 6;
    //如果为超级管理员
    if (roleType == 1) {
        minLength = 8
    }

    if (pwdVal.length < minLength) {
        result = 0;
        return result;
    }

    if (pwdVal.match(/\s/ig)) {
        result = 5;
        return result;
    }

    //匹配字母
    if (pwdVal.match(/[a-z]/ig)) {
        result++;
    }
    //数字
    if (pwdVal.match(/[0-9]/ig)) {
        result++;
    }
    //((?=[\x21-\x7e]+)[^A-Za-z0-9])
    if (pwdVal.match(/((?=[\x21-\x7e]+)[^A-Za-z0-9])/ig)) {
        result++;
    }
    /**校验完成是否存在两种字符（且不包括空格）**/
    if (roleType == 1 && result < 2) {
        result = 8;
        return result;
    } else if (roleType == 1) {
        result = 9;
        return result;
    }

    //alert(parseInt(result));
    //判断只用一种情况下
    if (result == 1) {
        //判断字符是否少于三种
        var array = pwdVal.split("");

        var temp_val = new Array();
        temp_val.push(array[0]);
        for (var i = 1; i < array.length; i++) {
            var flag = true;
            for (var j = 0; j < temp_val.length; j++) {
                if (temp_val[j] == array[i]) {
                    flag = false;
                }
            }
            if (flag) {
                temp_val.push(array[i]);
            }
        }
        //判断temp_val长度，计算出不重复字符的个数 (只包含数字，字母，符号中的一种，且字符少于三种；（222333不通过，222334通过)
        if (temp_val.length < 3) {
            result = 4;
            return result;
        }
        //只包含数字，字母，符号中的一种，且字符按照ASCII顺序或者反序排列。 (234567  abcdef不通过)
        var temp_add = array[0];
        var temp_subtract = array[0];
        var tempAscii = temp_add.charCodeAt();
        try {
            for (var i = 1; i < array.length; i++) {
                temp_add += String.fromCharCode(tempAscii + i);
                temp_subtract += String.fromCharCode(tempAscii - i);
            }
        } catch (e) {
        }
        if (temp_add == pwdVal || temp_subtract == pwdVal) {
            result = 6;
            return result;
        }

        //只包含数字，字母，符号中的一种，且不属于"弱"中的情形(不属于以上前两)
        result = 7;	//即 等于

    }

    return result;
}

function qqloginSetCookie() {
    //begin 设置cookei用来记录登陆时的域名，用做登陆出错和超时退出时跳到该域名
    var myhost = document.domain;
    var basedomain = "webtrn.cn";
    if (myhost.indexOf(".demo.") >= 0) {
        basedomain = "demo.webtrn.cn";
    }
    var backUrl = "http://" + myhost + "/cms/"
    $.cookies.set("site_project_backUrl", backUrl, {hoursToLive: 24 * 30, domain: basedomain, path: '/'});
    //end 设置cookei用来记录登陆时的域名，用做登陆出错和超时退出时跳到该域名
}

//判断是否是ios端
function isIosMobileClient() {
    var userAgentInfo = navigator.userAgent;
    var Agents = new Array("iPhone", "iPad", "iPod");
    var agentinfo = null;
    for (var i = 0; i < Agents.length; i++) {
        if (userAgentInfo.indexOf(Agents[i]) > 0) {
            agentinfo = userAgentInfo;
            break;
        }
    }
    if (agentinfo) {
        return true;
    } else {
        return false;
    }
}

//判断是否是微信中的浏览器
function isWeixinClient() {
    var ua = navigator.userAgent.toLowerCase();
    if (ua.match(/MicroMessenger/i) == "micromessenger") {
        return true;
    }
    return false;
}

/**
 * 获取手机登录验证码
 */
var errCount = 0;

function getVerifyCode() {
    var siteCode = $("#siteCode").val();
    var phone = $("#phone").val().trim()
    var timer = ''
    var t = 60
    if (!siteCode) {
        siteCode = 'typxNew'
    }

    var myParam = {
        "page.searchItem.loginId": phone,
        "page.searchItem.siteCode": siteCode
    }

    if(canAutoRes){
        myParam["canAutoRes"] = 'yes'
    }
    $.ajax({
        type: 'post',
        url: '/o/user/getVerifyCode.json',
        dataType: "json",
        data: myParam,
        success: function (data) {
            errCount = 0;
            $("#yzm").val("");

            if (data && data.status && data.status == '1') {
                $("#YanZM").removeAttr("onclick");
                document.getElementById("YanZM").onclick = "";
                var color = $("#YanZM").css('color')
                timer = setInterval(function () {
                    if (t < 1) {
                        t = 60
                        $("#YanZM").css('color', color)
                        $("#YanZM").html('重发验证码');
                        $("#YanZM").attr("onclick", "getMobileCode();");
                        clearInterval(timer)
                    } else {
                        t--
                        $("#YanZM").css('color', '#666')
                        $("#YanZM").html(t + '秒后重试')
                    }
                }, 1000)
            } else {
                if("手机号错误或异常!"==data.msg){
                    showMsg('', '此手机号暂未绑定账号')
                }else{
                    showMsg('', data.msg)
                }
            }
        }
    });
}

/**
 * 手机验证码登录
 */
function phoneLoginVerifyCode(portal) {
    var siteCode = $("#siteCode").val();
    var phoneReg = /^1[3-9]\d{9}$/
    var phone = $("#phone").val().trim()
    if (!phone) {
        showMsg('', '手机号码不能为空')
        return
    } else if (!phoneReg.test(phone)) {
        showMsg('', '请输入正确的手机号码')
        return
    }

    var verifyCode = $("#yzm").val().trim()
    if (!verifyCode) {
        showMsg('', '验证码不能为空')
        return;
    }
    var params = null;
    if (errCount >= 2) {
        params = {
            "page.searchItem.loginId": phone,
            "page.searchItem.verifyCode": verifyCode,
            "page.searchItem.siteCode": siteCode,
            "page.searchItem.isValidCode": 'true'
        }
    } else {
        params = {
            "page.searchItem.loginId": phone,
            "page.searchItem.verifyCode": verifyCode,
            "page.searchItem.siteCode": siteCode
        }
    }

    // 开启验证码登录自动注册
    if(canAutoRes){
        params["page.searchItem.canAutoRes"] = 'yes'
    }
    $.ajax({
        type: 'post',
        url: '/o/user/phoneLoginVerifyCodeAllRole.json',
        dataType: "json",
        data: params,
        async: false,
        success: function (data) {
            if (data && data.status && data.status == '1') {
                var roleCount = 0
                var studentId = data.studentId;
                var teacherId = data.teacherId;
                var managerId = data.managerId;
                var loginId;
                var password;
                var paramRole = {sendCode : '1', portal : portal}
                if(studentId){
                    roleCount++
                    loginId = studentId
                    password = data.studentPwd
                    paramRole['roleStudent'] = '1'
                    paramRole['studentId'] = studentId
                    paramRole['studentPwd'] = data.studentPwd
                }
                if(teacherId){
                    roleCount++
                    loginId = teacherId
                    password = data.teacherPwd
                    paramRole['roleTeacher'] = '1'
                    paramRole['teacherId'] = teacherId
                    paramRole['teacherPwd'] = data.teacherPwd
                }
                if(managerId){
                    roleCount++
                    loginId = managerId
                    password = data.managerPwd
                    paramRole['roleManager'] = '1'
                    paramRole['managerId'] = managerId
                    paramRole['managerPwd'] = data.managerPwd
                }
                if(roleCount>1){
                    $.cookies.set('paramRole',paramRole);
                    showRoleLogin(paramRole)
                }else{
                    var param = {
                        loginId: loginId,
                        password: password,
                        queckFlag: '1',
                        pwd: password,
                        portal: portal,
                        loginModule: '1',
                        flagPhoneLogin: '1'
                    }
                    loginCenter(param)
                }
            } else {
                if (data.msg === '验证码输入有误或者超时!' || data.msg === '验证码错误!' || data.msg === '验证码超时!') {
                    errCount++;
                }
                showMsg('', data.msg)
            }
        }
    });
}

function phoneLoginVerifyCodeNew(portal) {
    var siteCode = $("#siteCode").val();
    var phoneReg = /^1[3-9]\d{9}$/
    var phone = $("#phone").val().trim()
    if (!phone) {
        showMsg('', '手机号码不能为空')
        return
    } else if (!phoneReg.test(phone)) {
        showMsg('', '请输入正确的手机号码')
        return
    }

    var verifyCode = $("#yzm").val().trim();
    if (!verifyCode) {
        showMsg('', '验证码不能为空')
        return;
    }
    var params = null;
    if (errCount >= 2) {
        params = {
            "page.searchItem.loginId": phone,
            "page.searchItem.verifyCode": verifyCode,
            "page.searchItem.siteCode": siteCode,
            "page.searchItem.isValidCode": 'true'
        }
    } else {
        params = {
            "page.searchItem.loginId": phone,
            "page.searchItem.verifyCode": verifyCode,
            "page.searchItem.siteCode": siteCode
        }
    }

    // 开启验证码登录自动注册
    if(canAutoRes){
        params["page.searchItem.canAutoRes"] = 'yes'
    }
    $.ajax({
        type: 'post',
        url: '/o/user/phoneLoginVerifyCodeAllRole.json',
        dataType: "json",
        data: params,
        async: false,
        success: function (data) {
            if (data && data.status && data.status == '1') {
                var roleCount = 0
                var studentId = data.studentId;
                var teacherId = data.teacherId;
                var managerId = data.managerId;
                var bindUnionid = $.cookies.get("bindUnionid");
                var loginId;
                var password;
                var paramRole = {sendCode : '1', portal : portal}
                if(studentId){
                    roleCount++
                    loginId = studentId
                    password = data.studentPwd
                    paramRole['roleStudent'] = '1'
                    paramRole['studentId'] = studentId
                    paramRole['studentPwd'] = data.studentPwd
                }
                if(teacherId){
                    roleCount++
                    loginId = teacherId
                    password = data.teacherPwd
                    paramRole['roleTeacher'] = '1'
                    paramRole['teacherId'] = teacherId
                    paramRole['teacherPwd'] = data.teacherPwd
                }
                if(managerId){
                    roleCount++
                    loginId = managerId
                    password = data.managerPwd
                    paramRole['roleManager'] = '1'
                    paramRole['managerId'] = managerId
                    paramRole['managerPwd'] = data.managerPwd
                }
                if(roleCount>1){
                    $.cookies.set('paramRole',paramRole);
                    showRoleLogin(paramRole)
                }else{
                    var param = {
                        loginId: loginId,
                        password: password,
                        queckFlag: '1',
                        pwd: password,
                        portal: portal,
                        loginModule: '1',
                        flagPhoneLogin: '1',
                        unionId:bindUnionid
                    }
                    loginCenter(param)
                }
            } else {
                if (data.msg === '验证码输入有误或者超时!' || data.msg === '验证码错误!' || data.msg === '验证码超时!') {
                    errCount++;
                }
                showMsg('', data.msg)
            }
        }
    });
}



//md5 begin
var hex_chr = '0123456789abcdef';

function rhex(num) {
    str = "";
    for (j = 0; j <= 3; j++)
        str += hex_chr.charAt((num >> (j * 8 + 4)) & 0x0F) + hex_chr.charAt((num >> (j * 8)) & 0x0F);
    return str;
}

function str2blks_MD5(str) {
    nblk = ((str.length + 8) >> 6) + 1;
    blks = new Array(nblk * 16);
    for (i = 0; i < nblk * 16; i++)
        blks[i] = 0;
    for (i = 0; i < str.length; i++)
        blks[i >> 2] |= str.charCodeAt(i) << ((i % 4) * 8);
    blks[i >> 2] |= 0x80 << ((i % 4) * 8);
    blks[nblk * 16 - 2] = str.length * 8;
    return blks;
}

function add(x, y) {
    var lsw = (x & 0xFFFF) + (y & 0xFFFF);
    var msw = (x >> 16) + (y >> 16) + (lsw >> 16);
    return (msw << 16) | (lsw & 0xFFFF);
}

function rol(num, cnt) {
    return (num << cnt) | (num >>> (32 - cnt));
}

function cmn(q, a, b, x, s, t) {
    return add(rol(add(add(a, q), add(x, t)), s), b);
}

function ff(a, b, c, d, x, s, t) {
    return cmn((b & c) | ((~b) & d), a, b, x, s, t);
}

function gg(a, b, c, d, x, s, t) {
    return cmn((b & d) | (c & (~d)), a, b, x, s, t);
}

function hh(a, b, c, d, x, s, t) {
    return cmn(b ^ c ^ d, a, b, x, s, t);
}

function ii(a, b, c, d, x, s, t) {
    return cmn(c ^ (b | (~d)), a, b, x, s, t);
}

function MD5(str) {
    if (str.length == 0) {
        return str;
    }
    x = str2blks_MD5(str);
    var a = 1732584193;
    var b = -271733879;
    var c = -1732584194;
    var d = 271733878;

    for (i = 0; i < x.length; i += 16) {
        var olda = a;
        var oldb = b;
        var oldc = c;
        var oldd = d;

        a = ff(a, b, c, d, x[i + 0], 7, -680876936);
        d = ff(d, a, b, c, x[i + 1], 12, -389564586);
        c = ff(c, d, a, b, x[i + 2], 17, 606105819);
        b = ff(b, c, d, a, x[i + 3], 22, -1044525330);
        a = ff(a, b, c, d, x[i + 4], 7, -176418897);
        d = ff(d, a, b, c, x[i + 5], 12, 1200080426);
        c = ff(c, d, a, b, x[i + 6], 17, -1473231341);
        b = ff(b, c, d, a, x[i + 7], 22, -45705983);
        a = ff(a, b, c, d, x[i + 8], 7, 1770035416);
        d = ff(d, a, b, c, x[i + 9], 12, -1958414417);
        c = ff(c, d, a, b, x[i + 10], 17, -42063);
        b = ff(b, c, d, a, x[i + 11], 22, -1990404162);
        a = ff(a, b, c, d, x[i + 12], 7, 1804603682);
        d = ff(d, a, b, c, x[i + 13], 12, -40341101);
        c = ff(c, d, a, b, x[i + 14], 17, -1502002290);
        b = ff(b, c, d, a, x[i + 15], 22, 1236535329);

        a = gg(a, b, c, d, x[i + 1], 5, -165796510);
        d = gg(d, a, b, c, x[i + 6], 9, -1069501632);
        c = gg(c, d, a, b, x[i + 11], 14, 643717713);
        b = gg(b, c, d, a, x[i + 0], 20, -373897302);
        a = gg(a, b, c, d, x[i + 5], 5, -701558691);
        d = gg(d, a, b, c, x[i + 10], 9, 38016083);
        c = gg(c, d, a, b, x[i + 15], 14, -660478335);
        b = gg(b, c, d, a, x[i + 4], 20, -405537848);
        a = gg(a, b, c, d, x[i + 9], 5, 568446438);
        d = gg(d, a, b, c, x[i + 14], 9, -1019803690);
        c = gg(c, d, a, b, x[i + 3], 14, -187363961);
        b = gg(b, c, d, a, x[i + 8], 20, 1163531501);
        a = gg(a, b, c, d, x[i + 13], 5, -1444681467);
        d = gg(d, a, b, c, x[i + 2], 9, -51403784);
        c = gg(c, d, a, b, x[i + 7], 14, 1735328473);
        b = gg(b, c, d, a, x[i + 12], 20, -1926607734);

        a = hh(a, b, c, d, x[i + 5], 4, -378558);
        d = hh(d, a, b, c, x[i + 8], 11, -2022574463);
        c = hh(c, d, a, b, x[i + 11], 16, 1839030562);
        b = hh(b, c, d, a, x[i + 14], 23, -35309556);
        a = hh(a, b, c, d, x[i + 1], 4, -1530992060);
        d = hh(d, a, b, c, x[i + 4], 11, 1272893353);
        c = hh(c, d, a, b, x[i + 7], 16, -155497632);
        b = hh(b, c, d, a, x[i + 10], 23, -1094730640);
        a = hh(a, b, c, d, x[i + 13], 4, 681279174);
        d = hh(d, a, b, c, x[i + 0], 11, -358537222);
        c = hh(c, d, a, b, x[i + 3], 16, -722521979);
        b = hh(b, c, d, a, x[i + 6], 23, 76029189);
        a = hh(a, b, c, d, x[i + 9], 4, -640364487);
        d = hh(d, a, b, c, x[i + 12], 11, -421815835);
        c = hh(c, d, a, b, x[i + 15], 16, 530742520);
        b = hh(b, c, d, a, x[i + 2], 23, -995338651);

        a = ii(a, b, c, d, x[i + 0], 6, -198630844);
        d = ii(d, a, b, c, x[i + 7], 10, 1126891415);
        c = ii(c, d, a, b, x[i + 14], 15, -1416354905);
        b = ii(b, c, d, a, x[i + 5], 21, -57434055);
        a = ii(a, b, c, d, x[i + 12], 6, 1700485571);
        d = ii(d, a, b, c, x[i + 3], 10, -1894986606);
        c = ii(c, d, a, b, x[i + 10], 15, -1051523);
        b = ii(b, c, d, a, x[i + 1], 21, -2054922799);
        a = ii(a, b, c, d, x[i + 8], 6, 1873313359);
        d = ii(d, a, b, c, x[i + 15], 10, -30611744);
        c = ii(c, d, a, b, x[i + 6], 15, -1560198380);
        b = ii(b, c, d, a, x[i + 13], 21, 1309151649);
        a = ii(a, b, c, d, x[i + 4], 6, -145523070);
        d = ii(d, a, b, c, x[i + 11], 10, -1120210379);
        c = ii(c, d, a, b, x[i + 2], 15, 718787259);
        b = ii(b, c, d, a, x[i + 9], 21, -343485551);

        a = add(a, olda);
        b = add(b, oldb);
        c = add(c, oldc);
        d = add(d, oldd);
    }
    return rhex(a) + rhex(b) + rhex(c) + rhex(d);
}


function doCheckPersonalDataEditCondition() {
    var needEditKeyNameList = []
    $.ajax({
        url: '/u/user/queryUserPersonalDataEditStatus.json',
        dataType: 'json',
        type: 'post',
        async: false,
        success: function (data) {
            needEditKeyNameList = data.data.needEditKeyNameList
        },
        error: function () {
        }
    })
    return needEditKeyNameList
}
//展示角色
function showRoleLogin(data) {
    var teacherFlag = '0';
    var studentFlag = '0';
    var managerFlag = '0';
    var sendCode = '0';
    if("1" == data.roleTeacher){
        teacherFlag = '1'
    }
    if("1" == data.roleStudent){
        studentFlag = '1'
    }
    if("1" == data.roleManager){
        managerFlag = '1'
    }
    if("1" == data.sendCode){
        sendCode = '1'
    }
    parent.layer.open({
        type: 2,
        title: false,
        shadeClose: false,
        shade: 0.5,
        maxmin: false, //开启最大化最小化按钮
        closeBtn: 0,
        area: ['472px', '322px'],
        content: '/cms/role.htm?teacherFlag=' + teacherFlag + '&studentFlag=' + studentFlag + '&managerFlag=' + managerFlag + '&sendCode=' + sendCode,
        success: function(layero, index){}
    });
}
//选择角色登录
function chooseRoleDoSubmit(role) {
    var data = $.cookies.get("chooseRoleData")
    data['role'] = role
    $.cookies.set("chooseRoleData",{})
    /********************login start*********************/
    loginCenter(data);
    /*******************login end**********************/
}
//选择角色登录
function chooseRoleDoSubmitSendCode(role) {
    var data = $.cookies.get("paramRole")
    var loginId;
    var password;
    if('student'==role){
        loginId = data['studentId']
        password = data['studentPwd']
    }else if('teacher'==role){
        loginId = data['teacherId']
        password = data['teacherPwd']
    }else if('manager'==role){
        loginId = data['managerId']
        password = data['managerPwd']
    }
    var param = {
        loginId: loginId,
        password: password,
        queckFlag: '1',
        pwd: password,
        portal: data['portal'],
        loginModule: '1',
        flagPhoneLogin: '1'
    }
    $.cookies.set("paramRole",{})
    /********************login start*********************/
    loginCenter(param);
    /*******************login end**********************/
}

function returnRole(role) {
    if('student'==role){
        role = '0'
    }else if('teacher'==role){
        role = '1'
    }else if('manager'==role){
        role = '2'
    }
    return role;
}


function loginWXBind(toBackURL){
    var layerObj = layer.open({
        type: 2,
        title: false,
        shadeClose: true,
        closeBtn:false,
        shade: 0.5,
        maxmin: false, //开启最大化最小化按钮
        area: ['320px', '360px'],
        //area: ['305px', '340px'],
        //content: '/cms/login.htm?toBackURL='+toBackURL,
        content: '/cms/channelWxloginBindPhone.htm?v='+new Date().getTime(),
        success: function(layero, index){
            $(".layui-layer-ico.layui-layer-close.layui-layer-close2").css('transition', 'none')
            var $body = layer.getChildFrame('body', index);
            $body.find('#loginOfLayer').css("margin-left","25px").css("margin-right","25px");
            $body.find('#layui-layer1').css("border-radius","6px");
            $('#layui-layer1').css("border-radius","6px");
            $(".layui-layer-ico.layui-layer-close.layui-layer-close2").css('transition', 'none')
            $('.layui-layer.layui-layer-iframe.layer-anim').append('<div class="pop-login-close" onclick="layer.close(' + index + ')" data-role="popup-shut"><i class="iconfont icon-cuowu"></i></div>');

        }
    });
}

/**
 * 检查微信登录是否需要绑定手机号
 */
function wxBindLoginCallBackCheck(){
    try {
        var baseUrl = decodeURIComponent(window.location.href)
        var unionId = getQueryString('unionIdForLogin');
        var nickName = getQueryStringFCM('nickNameForWxBind')
        if (unionId) {
            localStorage.setItem("unionIdForWxBind", unionId);
            localStorage.setItem("nickNameForWxBind", nickName);
            loginWXBind()
            var resultUrl;
            if (typeof window.location.origin ==='undefined')
            {
                resultUrl = window.location.protocol + window.location.pathname;
            }else{
                resultUrl = window.location.origin + window.location.pathname;
            }
            window.history.pushState({}, '', resultUrl);
        } else {
            if (baseUrl.indexOf("unionIdForWxBind") > -1) {
                layer.alert("微信绑定登录失败，无法用户信息！")
            }
        }
    } catch (e) {
        console.log('检测是微信自动登录注册失败',e)
    }
}


function getQueryStringFCM(name) {
    var reg = new RegExp("(^|&)" + name + "=([^&]*)(&|$)", "i");
    var r = window.location.search.substr(1).match(reg);
    if (r != null) return decodeURIComponent(escape(r[2]));
    return null;
}

function verticalScrollIndexHeader(scrollname){
    if($(scrollname).length > 0) {
        $(scrollname).each(function(index) {
            $(this).mCustomScrollbar({
                // scrollbarPosition: "outside",
                theme: "minimal"
            });
        });

    }
}



//禁用滚动条
function unScrollHeader() {
    var top = $(document).scrollTop();
    $(document).on('scroll.unable',function (e) {
        $(document).scrollTop(top);
    })
}
//停止禁用滚动条
function removeUnScrollHeader() {
    $(document).unbind("scroll.unable");
}

function oepnThirdPop(txt){
    unScrollHeader()
    $("#thirdRegistTipFcmContent").html(txt)
    $("#thirdRegistTipFcm").show()
    verticalScrollIndexHeader('[data-scroll="vertical-scrollable-fan"]')
}
function closeThirdPop(){
    removeUnScrollHeader()
    $("#thirdRegistTipFcmContent").mCustomScrollbar("destroy");
    $("#thirdRegistTipFcm").hide();
}