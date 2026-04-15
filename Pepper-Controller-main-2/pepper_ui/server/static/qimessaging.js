/* qimessaging.js - Pepper Compatible Version */
(function() {
    var _QiSession = function(ip) {
        this.socket = null;
        this._dfd = [];
        this._services = {};
        var _this = this;
        
        var host = ip || window.location.host.split(':')[0];
        
        // Connect to Pepper (Port 80)
        var url = "ws://" + host + ":80/2.0/socket.io/1/websocket/" + Math.random().toString(36).substring(2);
        console.log("Connecting to: " + url);

        try {
            this.socket = new WebSocket(url);
        } catch (e) { return; }

        this.socket.onopen = function() {
            while (_this._dfd.length > 0) {
                var callback = _this._dfd.shift();
                callback(_this);
            }
        };

        this.socket.onmessage = function(msg) {
            var data = JSON.parse(msg.data);
            if (data.id && _this._services[data.id]) {
                _this._services[data.id](data.result);
                delete _this._services[data.id];
            }
        };
    };

    _QiSession.prototype.service = function(serviceName) {
        var _this = this;
        return new Promise(function(resolve, reject) {
            var id = "s_" + Math.random().toString(36).substring(2);
            _this._services[id] = function(serviceObj) { resolve(serviceObj); };
            var payload = JSON.stringify({ type: "call", id: id, service: "ServiceDirectory", fn: "service", args: [serviceName] });
            if (_this.socket.readyState === 1) _this.socket.send(payload);
        });
    };

    window.QiSession = function(ip) { return new _QiSession(ip); };
})();