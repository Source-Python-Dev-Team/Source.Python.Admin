var PLUGIN = function () {
    var plugin = this;

    var ANIMATION_DURATION = 1000;

    var ReviewBanPage = function (banTableNode, reviewBanWrapNode, reviewBanNode, banIdNode, playerNameNode, playerUniqueidNode, reasonSelectNode, reasonTextareaNode, durationSelectNode, reviewButtonNode) {
        var reviewBanPage = this;

        var BanEntry = function (uniqueid, banId, name) {
            var banEntry = this;

            this.uniqueid = uniqueid;
            this.banId = banId;
            this.name = name;

            var lineNode;
            this.create = function (node) {
                lineNode = node.appendChild(document.createElement('div'));
                lineNode.classList.add('ban-table-line');

                var cellNode = lineNode.appendChild(document.createElement('div'));
                cellNode.appendChild(document.createTextNode(banEntry.uniqueid));
                cellNode.classList.add('ban-table-uniqueid');

                cellNode = lineNode.appendChild(document.createElement('div'));
                cellNode.appendChild(document.createTextNode(banEntry.name));
                cellNode.classList.add('ban-table-name');

                lineNode.style.animationName = "ban-table-row-add";

                lineNode.addEventListener('click', function (e) {
                    if (banEntry.banId)
                        showPanel(banEntry.uniqueid, banEntry.banId, banEntry.name);
                });
            };
            this.destroy = function () {
                banEntry.banId = undefined;
                lineNode.style.animationName = "ban-table-row-remove";
                setTimeout(function () {
                    if (lineNode)
                        lineNode.parentNode.removeChild(lineNode);
                    lineNode = undefined;
                }, ANIMATION_DURATION);
            };
            this.destroyNoDelay = function () {
                banEntry.banId = undefined;
                lineNode.parentNode.removeChild(lineNode);
                lineNode = undefined;
            };
        };

        var banEntries = [];

        banTableNode.classList.add('ban-table');
        reviewBanNode.classList.add('review-ban');
        reviewBanWrapNode.classList.add('review-ban-wrap');
        reviewButtonNode.classList.add('review-button');

        var clearBans = function () {
            banEntries.forEach(function (val, i, arr) {
                val.destroyNoDelay();
            });
            banEntries = [];
        };
        var addBan = function (uniqueid, banId, name) {
            removeBanId(banId);
            var banEntry = new BanEntry(uniqueid, banId, name);
            banEntry.create(banTableNode);
            banEntries.push(banEntry);
        };
        var removeBanId = function (banId) {
            var invalidEntries = [];
            banEntries.forEach(function (val, i, arr) {
                if (val.banId == banId)
                    invalidEntries.push(val);
            });
            invalidEntries.forEach(function (val, i, arr) {
                val.destroy();
                banEntries.splice(banEntries.indexOf(val), 1);
            });
        };

        var StockBanDuration = function (value, title) {
            stockBanDuration = this;

            this.value = value;
            this.title = title;
        };
        stockBanDurations = [];

        var StockBanReason = function (hiddenTitle, title, durationValue, durationTitle) {
            stockBanReason = this;

            this.hiddenTitle = hiddenTitle;
            this.title = title;
            this.durationValue = durationValue;
            this.durationTitle = durationTitle;
        };
        stockBanReasons = [];

        var mode = 'unknown';
        this.tryWS = function (wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback) {
            MOTDPlayer.openWSConnection(function () {
                mode = 'ws';
                requestBanData();
                if (wsSuccessCallback)
                    wsSuccessCallback();
            }, function (data) {
                switch (data['action']) {
                    case 'ban-data':
                        data['bans'].forEach(function (val, i, arr) {
                            addBan(val['uniqueid'], val['banId'], val['name']);
                        });
                        data['reasons'].forEach(function (val, i, arr) {
                            stockBanReasons.push(new StockBanReason(val['hidden'], val['title'], val['duration-value'], val['duration-title']));
                        });
                        data['durations'].forEach(function (val, i, arr) {
                            stockBanDurations.push(new StockBanDuration(val['value'], val['title']));
                        });
                        break;
                    case 'remove-ban-id':
                        removeBanId(data['banId']);
                        break;
                }
                if (wsMessageCallback)
                    wsMessageCallback(data);
            }, function () {
                clearBans();
                if (wsCloseCallback)
                    wsCloseCallback();
            }, function (err) {
                if (mode == 'unknown') {
                    mode = 'ajax';
                    requestBanData();
                }
                if (wsErrorCallback)
                    wsErrorCallback(err);
            });
        };

        var requestBanData = function () {
            switch (mode) {
                case 'ajax':
                    MOTDPlayer.post({
                        action: 'get-ban-data',
                    }, function (data) {
                        clearBans();
                        data['bans'].forEach(function (val, i, arr) {
                            addBan(val['uniqueid'], val['banId'], val['name']);
                        });
                        stockBanReasons = [];
                        data['reasons'].forEach(function (val, i, arr) {
                            stockBanReasons.push(new StockBanReason(val['hidden'], val['title'], val['duration-value'], val['duration-title']));
                        });
                        stockBanDurations = [];
                        data['durations'].forEach(function (val, i, arr) {
                            stockBanDurations.push(new StockBanDuration(val['value'], val['title']));
                        });
                    }, function (err) {
                        // TODO: Display error
                    });
                    break;

                case 'ws':
                    MOTDPlayer.sendWSData({
                        action: 'get-ban-data',
                    });
                    break;
            }
        };

        var execute = function (banId, reason, duration) {
            switch (mode) {
                case 'ajax':
                    MOTDPlayer.post({
                        action: 'execute',
                        banId: banId,
                        reason: reason,
                        duration: duration,
                    }, function (data) {
                        if (data['status'] == "ok") ;  // TODO: Display success popup
                        clearBans();
                        data['bans'].forEach(function (val, i, arr) {
                            addBan(val['uniqueid'], val['banId'], val['name']);
                        });
                    }, function (err) {
                        // TODO: Display error
                    });
                    break;

                case 'ws':
                    MOTDPlayer.sendWSData({
                        action: 'execute',
                        banId: banId,
                        reason: reason,
                        duration: duration,
                    });
                    break;
            }
        };

        var currentBanId;
        var showPanel = function (uniqueid, banId, name) {
            currentBanId = banId;

            reviewBanWrapNode.classList.add('visible');

            // Ban ID
            while (banIdNode.firstChild)
                banIdNode.removeChild(banIdNode.firstChild);

            banIdNode.appendChild(document.createTextNode("" + banId));

            // Player Name
            while (playerNameNode.firstChild)
                playerNameNode.removeChild(playerNameNode.firstChild);

            playerNameNode.appendChild(document.createTextNode(name));

            // Player UniqueID
            while (playerUniqueidNode.firstChild)
                playerUniqueidNode.removeChild(playerUniqueidNode.firstChild);

            playerUniqueidNode.appendChild(document.createTextNode("" + uniqueid));

            // Reasons
            while (reasonSelectNode.firstChild)
                reasonSelectNode.removeChild(reasonSelectNode.firstChild);

            var optionNode = reasonSelectNode.appendChild(document.createElement('option'));
            optionNode.appendChild(document.createTextNode("** MY OWN REASON **"));
            optionNode.value = -1;

            stockBanReasons.forEach(function (val, i, arr) {
                var optionNode = reasonSelectNode.appendChild(document.createElement('option'));
                optionNode.appendChild(document.createTextNode(val.title));
                optionNode.value = i;
            });

            // Durations
            fillDurations();
        };

        var hidePanel = function () {
            currentBanId = undefined;
            reviewBanWrapNode.classList.remove('visible');
        };

        var fillDurations = function (reasonDurationValue, reasonDurationTitle) {
            while (durationSelectNode.firstChild)
                durationSelectNode.removeChild(durationSelectNode.firstChild);

            var optionNode = durationSelectNode.appendChild(document.createElement('option'));
            optionNode.appendChild(document.createTextNode("Select duration..."));
            optionNode.disabled = true;
            optionNode.value = 0;

            if (reasonDurationValue && reasonDurationTitle) {
                optionNode = durationSelectNode.appendChild(document.createElement('option'));
                optionNode.appendChild(document.createTextNode("(default) " + reasonDurationTitle));
                optionNode.value = reasonDurationTitle;
            }

            stockBanDurations.forEach(function (val, i, arr) {
                var optionNode = durationSelectNode.appendChild(document.createElement('option'));
                optionNode.appendChild(document.createTextNode(val.title));
                optionNode.value = val.value;
            });
        };

        reviewBanWrapNode.addEventListener('click', function (e) {
            hidePanel();
        });
        reviewBanNode.addEventListener('click', function (e) {
            e.stopPropagation();
        });
        reasonSelectNode.addEventListener('change', function (e) {
            if (this.value == -1) {
                reasonTextareaNode.disabled = false;
                fillDurations();
            }
            else {
                reasonTextareaNode.disabled = true;

                var stockBanReason = stockBanReasons[this.value];
                fillDurations(stockBanReason.durationValue, stockBanReason.durationTitle);
            }
        });
        reviewButtonNode.addEventListener('click', function (e) {
            var reason;
            if (reasonSelectNode.value == -1)
                reason = reasonTextareaNode.value;
            else
                reason = stockBanReasons[reasonSelectNode.value].hiddenTitle;

            var duration = durationSelectNode.value;

            if (currentBanId && reason && duration != 0) {
                execute(currentBanId, reason, parseInt(duration));
                hidePanel();
            };
        });
    };

    this.init = function (banTableNode, reviewBanWrapNode, reviewBanNode, banIdNode, playerNameNode, playerUniqueidNode, reasonSelectNode, reasonTextareaNode, durationSelectNode, reviewButtonNode, wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback) {
        reviewBanPage = new ReviewBanPage(banTableNode, reviewBanWrapNode, reviewBanNode, banIdNode, playerNameNode, playerUniqueidNode, reasonSelectNode, reasonTextareaNode, durationSelectNode, reviewButtonNode);
        reviewBanPage.tryWS(wsSuccessCallback, wsMessageCallback, wsCloseCallback, wsErrorCallback);
    };
};
