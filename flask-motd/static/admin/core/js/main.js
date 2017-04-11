var APP = function (version, author, serverTime, b64NavInit) {
    var app = this;

    var NAV_LINK_HEIGHT = 25, NAV_BAR_HEIGHT = 30;
    var MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var navData = JSON.parse(atob(b64NavInit));
    navData.originalPath = navData.currentPath === null ? null : navData.currentPath.slice();

    var clientTimeDiff = Date.now() - serverTime;

    var NavSection = function (obj) {
        var navSection = this;

        this.id = obj.id;
        this.title = obj.title;
        this.selectable = obj.selectable;
        this.switchesTo = obj.switchesTo;
        this.navPath = obj.navPath;
        this.subSections = {};

        obj.subNavs.forEach(function (val, i, arr) {
            var subNavSection = new NavSection(val);
            navSection.subSections[subNavSection.id] = subNavSection;
        });

        this.getTitleNode = function () {
            var titleNode = document.createElement('div');
            titleNode.classList.add('nav-section-title');
            titleNode.appendChild(document.createTextNode(navSection.title));
            titleNode.addEventListener('click', function (e) {
                if (navSection.navPath == navData.currentPath)
                    return;

                selectNavSection(navSection);
            });
            return titleNode;
        };

        this.getLinkNode = function () {
            var linkNode = document.createElement('div');
            linkNode.classList.add('nav-section-link');
            linkNode.appendChild(document.createTextNode(navSection.title));
            linkNode.addEventListener('click', function (e) {
                selectNavSection(navSection);
            });
            return linkNode;
        };
    };

    var globalNav = new NavSection(navData.navData);

    var systemStatusNode;
    this.showSystemStatus = function () {
        if (!mainNode)
            return;

        if (systemStatusNode)
            return;

        systemStatusNode = mainNode.appendChild(document.createElement('div'));
        systemStatusNode.classList.add('system-status');

        var text = "";
        text += "Source.Python Admin v" + version + " by " + author + " • ";
        text += "Your SteamID64: " + MOTDPlayer.getPlayerSteamID64();

        systemStatusNode.appendChild(document.createTextNode(text));
    };

    this.hideSystemStatus = function () {
        if (!systemStatusNode)
            return;

        mainNode.removeChild(systemStatusNode);
        systemStatusNode = undefined;
    };

    var padded = function (value, pad) {
        return ("0000" + value).substr(-pad);
    }

    var serverClockNode;
    var updateServerClock = function () {
        var dt = new Date(Date.now() - clientTimeDiff);

        if (serverClockNode.firstChild)
            serverClockNode.removeChild(serverClockNode.firstChild);

        var text = MONTH_NAMES[dt.getMonth()] + " " + padded(dt.getDate(), 2) + ", " + dt.getFullYear() + " " + padded(dt.getHours(), 2) + ":" + padded(dt.getMinutes(), 2) + ":" + padded(dt.getSeconds(), 2);
        serverClockNode.appendChild(document.createTextNode(text));
    };

    var serverClockInterval;
    this.showServerClock = function () {
        if (serverClockInterval)
            return;

        serverClockNode = mainNode.appendChild(document.createElement('div'));
        serverClockNode.classList.add('server-clock');

        updateServerClock();
        serverClockInterval = setInterval(updateServerClock, 1000);
    };

    this.hideServerClock = function () {
        if (!serverClockInterval)
            return;

        clearInterval(serverClockInterval);
        serverClockInterval = undefined;

        mainNode.removeChild(serverClockNode);
        serverClockNode = undefined;
    };

    var navBarNode, navBarLinksNum = 0, currentNavSection;
    this.initNavBar = function () {
        if (navBarNode)
            return;

        navBarNode = navAreaNode.appendChild(document.createElement('div'));
        navBarNode.classList.add('nav-section-bar');
        navBarNode.addEventListener('mouseleave', function (e) {
            navBarNode.style.height = '';
        });
        navBarNode.addEventListener('mouseenter', function (e) {
            navBarNode.style.height = (NAV_BAR_HEIGHT + NAV_LINK_HEIGHT * navBarLinksNum) + 'px';
        });
        app.updateNavBar();
    };

    this.updateNavBar = function () {
        if (!navBarNode)
            return;

        while (navBarNode.firstChild)
            navBarNode.removeChild(navBarNode.firstChild);

        var navTitleContainer = navBarNode.appendChild(document.createElement('div'));
        navTitleContainer.classList.add('nav-section-title-container');

        currentNavSection = globalNav;
        navTitleContainer.appendChild(currentNavSection.getTitleNode());
        if (navData.currentPath !== null) {
            navData.currentPath.forEach(function (val, i, arr) {
                currentNavSection = currentNavSection.subSections[val];
                var breaker = navTitleContainer.appendChild(document.createElement('div'));
                breaker.innerHTML = "&raquo;";  // createTextNode doesn't parse HTML entities
                breaker.classList.add('nav-section-bar-breaker');

                navTitleContainer.appendChild(currentNavSection.getTitleNode());
            });
        }

        navBarNode.appendChild(document.createElement('div')).classList.add('clear');

        navBarLinksNum = 0;

        for (var id in currentNavSection.subSections) {
            navBarLinksNum++;
            navBarNode.appendChild(currentNavSection.subSections[id].getLinkNode());
        }
    };

    var selectNavSection = function (navSection) {
        if (navSection.switchesTo === null || navSection.switchesTo == MOTDPlayer.getPageId()) {
            app.setCurrentPath(navSection.navPath)
            return;
        }
        MOTDPlayer.switchPage(navSection.switchesTo, function () {
            MOTDPlayer.reloadPage();
        }, function (err) {
            // TODO: Report the error
        });
    };

    this.getClientTimeDiff = function () {
        return clientTimeDiff;
    };

    this.getVersion = function () {
        return version;
    };

    this.getAuthor = function () {
        return author;
    };

    this.isSamePath = function (path1, path2) {
        if (path1 === null)
            return path2 === null;

        if (path2 === null)
            return path1 === null;

        if (path1.length != path2.length)
            return false;

        var samePath = true;
        for (var i = 0; i < path1.length; i++)
            if (path1[i] != path2[i]) {
                samePath = false;
                break;
            }

        return samePath;
    };

    this.getCurrentPath = function () {
        return navData.currentPath.slice();
    };

    this.setCurrentPath = function (newPath) {
        if (app.isSamePath(newPath, navData.currentPath))
            return;

        navData.currentPath = newPath;
        app.updateNavBar();

        var pathChangedEvent = new Event('PathChanged');
        document.dispatchEvent(pathChangedEvent);
    };

    this.getPathLoadedWith = function () {
        return navData.originalPath;
    };

    var mainNode, navAreaNode;
    document.addEventListener('DOMContentLoaded', function (e) {
        mainNode = document.getElementById('main');
        navAreaNode = document.getElementById('nav-area');
        app.showSystemStatus();
        app.showServerClock();
        app.initNavBar();

        var appInitEvent = new Event('AppInit');
        document.dispatchEvent(appInitEvent);
    });
};
