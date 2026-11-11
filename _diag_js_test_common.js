<!doctype html>
<html>
<head>
    <script type="text/javascript">
        function getRootPath() {
            var strFullPath = window.document.location.href;
            var strPath = window.document.location.pathname;
            var pos = strFullPath.indexOf(strPath);
            var prePath = strFullPath.substring(0, pos);
            var postPath = strPath.substring(0, strPath.substr(1).indexOf('/') + 1);
            return (prePath + postPath);
        }
        document.write('<link href="'+ getRootPath() + '/resource/error/css/cbb-errorpage.css" rel="stylesheet" type="text/css">');
    </script>
    <meta charset="utf-8">
    <title>无标题文档</title>
</head>


<body>
    <!-------------------- errorpage start ---------------------->
    <div class="cbb-errorpage">
        <div class="cbb-errorpage-wrap">
            <div class="cbb-error-img error-404"></div>
            <h3 class="cbb-error-title">抱歉，您访问的页面不存在</h3>
            <div class="cbb-error-spell">Sorry, the page you visited does not exist.</div>
            <div class="btn-group">
                <a href="javascript:window.history.back();" class="btn btn-hollow-primary">返回</a>
            </div>
        </div>
    </div>
    <!-------------------- errorpage end ---------------------->
</body>
</html>
