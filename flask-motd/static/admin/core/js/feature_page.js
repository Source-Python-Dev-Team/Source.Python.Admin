var PLUGIN = function () {
    var plugin = this;

    var FeaturePage = function () {
        var featurePage = this;

        this.execute = function () {
            MOTDPlayer.post({
                action: 'execute',
            }, function (data) {
                if (data['status'] == "ok") ;  // TODO: Display success popup
                app.setCurrentPath(app.getCurrentPath().slice(0, -1));
            }, function (err) {
                // TODO: Display error
            });
        };
    };

    var featurePage;
    this.init = function () {
        featurePage = new FeaturePage();
        featurePage.execute();
    };

    document.addEventListener('AppInit', function (e) {
        plugin.init();

        var pluginInitEvent = new Event('PluginInit');
        document.dispatchEvent(pluginInitEvent);
    });

    document.addEventListener('PathChanged', function (e) {
        if (app.isSamePath(app.getPathLoadedWith(), app.getCurrentPath()))
            featurePage.execute();
    });
};
