Cooleur=(function() {
    var _Cooleur={},
        M=Math,
        intVal = M.floor,
        XFF=255,
        HEX_CHARS="0123456789ABCDEF",
        getInt=function(x,d){
        x=parseInt(x,10);
            return isNaN(x)?getInt(d,0):x;
        },
        randInt=function(n){
            return intVal(M.random()*n);
        },
        randSign=function(){
            return M.random()>0.5?1:-1;
        },
        hueToRgb=function(p, q, t){
            if(t<=0){t+=1;}
            if(t>=1){t-=1;}
            if(t<1/6){return p+(q-p)*6*t;}
            if(t<1/2){return q;}
            if(t<2/3){return p+(q-p)*(2/3-t)*6;}
            return p;
        },
        hexChar=function(x){
            return HEX_CHARS.charAt(x&15)
        },
        byteToHex = function(N) {
            return hexChar(N>>4)+hexChar(N&15);
        },
        now = function(){
            return +new Date;
        };
    var Color = _Cooleur.Color=function(rgb){
        var    _rgb = rgb||[0,0,0],
            _Color={};
        _Color.fromHsl = function(h,s,l){
            var r, g, b;
            if(s === 0){
                r=g=b=l;
            }else{
                var q = l<0.5?l*(1+s):l+s-l*s;
                var p = 2 * l - q;
                r = hueToRgb(p, q, h + 1/3);
                g = hueToRgb(p, q, h);
                b = hueToRgb(p, q, h - 1/3);
            }
            _rgb=[r*XFF,g*XFF,b*XFF];
            return this;
        };
        _Color.red=_Color.r=function(){
            return _rgb[0];
        };
        _Color.green=_Color.g=function(){
            return _rgb[1];
        };
        _Color.blue=_Color.b=function(){
            return _rgb[2];
        };
        _Color.rgbArray=function(){
            return _rgb;
        };
        _Color.hex=_Color.toString=function(){
            return "#"+byteToHex(_rgb[0])+byteToHex(_rgb[1])+byteToHex(_rgb[2]);
        };
        _Color.hsl=function(){
            var r=_rgb[0]/XFF,g=_rgb[1]/XFF,b=_rgb[2]/XFF,
                h,s,l,max,min,d;
            max=M.max(r,g,b);
            min=M.min(r,g,b);
            l=(max+min)/2;
            if(max==min){
                h=s=0;
            }else{
                d=max-min;
                s=l>0.5?d/(2-max-min):d/(max+min);
                if(max==r){
                    h=(g-b)/d+(g<b?6:0);
                }else if(max==g){
                    h=(b-r)/d+2;
                }else{
                    h=(r-g)/d+4;
                }
                h/=6;
            }
            return [h,s,l];
        };
        _Color.hue=_Color.h=function(){
            return this.hsl()[0];
        };
        _Color.saturation=_Color.s=function(){
            return this.hsl()[1];
        };
        _Color.lightness=_Color.l=function(){
            return this.hsl()[2];
        };
        return _Color;
    }
    var heatColor = _Cooleur.heatColor=function(x){
        return Color().fromHsl((1/3-x/3)%1, 1, 0.5);
    };
    var candyColor = _Cooleur.candyColor=function(x){
        x=getInt(x,randInt(32));
        var a=1524,b=12,c=7,d=127,
        h=((intVal((((x*c)%b)*a)/b)+intVal(x/b)%d)%a)/a,
        l=0.5+0.2*(intVal(x*(1+1.0/b))%3-1);
        return Color().fromHsl(h,1,l);
    };
    var Timer = _Cooleur.Timer = function(callback){
        var _Timer = {},
            last = now(),
            running = false,
            value = 0
            interval = null;
        _Timer.start = function() {
            running = true;
            interval = setInterval(this.read, 100)
            return this;
        };
        _Timer.stop = function() {
            running = true;
            clearInterval(interval)
            return this;
        };
        _Timer.read = function() {
            if (running) {
                value += now() - last;
            }
            last = now();
            if (typeof callback == "function") {
                return callback( value );
            }else{
                return value;
            }
        };
        return _Timer;
    }
    _Cooleur.Breather = function(period, callback) {
        period = getInt(period * 10, 20000);
        var cb = function(x) {
            var value = M.abs(M.sin(x / period * M.PI))
            if (typeof callback == "function") {
                return callback(value);
            }else{
                return value
            }
        }
        return Timer(cb);
    }
    _Cooleur.ColorGlower = function( period, callback ){
        var changingColor=randInt(3),
            dir=randSign(),
            last_update=0,
            rgb;
        period=M.max(1, getInt(period/100,10));
        rgb=[127,127,127]//Color().fromHsl(M.random(),1,0.5).rgbArray();
        var cb = function( t ) {
            var reset=false,
                sum_rgb,
                step=(t-last_update)*1.0/period,
                offset;
            last_update=t;
            offset=(randInt(step-1)+1)*dir
            rgb[changingColor]+=offset;
            rgb[changingColor]=M.max(M.min(rgb[changingColor],XFF),0);
            if(rgb[changingColor]===0||rgb[changingColor]==XFF){
                reset=true;
            }
            if(reset){
                sum_rgb=rgb[0]+rgb[1]+rgb[2];
                changingColor=randInt(2);
                if(sum_rgb==XFF){
                    if(rgb[0]==XFF){changingColor++;}
                    if(rgb[1]==XFF&&changingColor==1){changingColor++;}
                    dir=1;
                }else if(sum_rgb>=2*XFF){
                    if(rgb[0]===0){changingColor++;}
                    else if(rgb[1]===0&&changingColor==1){changingColor++;}
                    dir=-1;
                }else{
                    dir=1;
                    changingColor=randInt(3)
                }
            }
            if (typeof callback == "function") {
                return callback( Color(rgb) );
            }else{
                return Color(rgb);
            }
        }
        return Timer(cb);
    }
    _Cooleur.TextScroller = function(target, size, text, header, footer, fill) {
        var TS={},
            display_size, offset = 0,
            direction = 1,
            pause_duration = 3,
            pause_counter = 0,
            interval;
        header = header || "";
        footer = footer || "";
        fill = fill || true;
        display_size = size - header.length - footer.length;
        
        function showText() {
            if(!target.parentElement){
                clearInterval(interval);
                return;
            }
            if (display_size >= text.length) {
                if(fill) {
                    while(display_size>text.length){
                        text += " ";
                    }
                }
                target.innerHTML = header + text + footer;
            } else {
                target.innerHTML = header + text.substr(offset, display_size) + footer;
                offset += direction;
                if (direction === 0) {
                    if (pause_counter < pause_duration) {
                        pause_counter++;
                    } else {
                        pause_counter = 0;
                        if (offset + display_size >= text.length) {
                            direction = -1;
                        }
                        else if (offset === 0) {
                            direction = 1;
                        }
                    }
                } else if (offset + display_size >= text.length || offset === 0) {
                    direction = 0;
                }
            }
        }
        TS.start = function() {
            interval = setInterval(showText, 200);
            return this;
        };
        TS.stop = function() {
            clearInterval(interval);
            offset = 0;
            direction = 1;
            pause_counter = 0;
            showText();
            return this;
        };
        showText();
        return TS;
    };
    return _Cooleur;
})();
