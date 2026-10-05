export class DrawingManager {
  constructor(chart, host) {
    this.chart=chart; this.host=host; this.items=[]; this.mode="select";
    this.svg=document.createElementNS("http://www.w3.org/2000/svg","http://www.w3.org/2000/svg");
    this.svg.style.cssText="position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
    host.style.position="relative"; host.appendChild(this.svg);
    this.drag=null;
    host.addEventListener("pointerdown",e=>this.down(e));
    host.addEventListener("pointermove",e=>this.move(e));
    host.addEventListener("pointerup",e=>this.up(e));
    host.addEventListener("pointerleave",e=>this.up(e));
    this.render();
  }
  setMode(mode){this.mode=mode}
  point(e){
    const r=this.host.getBoundingClientRect();
    return {x:e.clientX-r.left,y:e.clientY-r.top};
  }
  model(p){
    const ts=this.chart.timeScale(), ps=this.chart.priceScale("right");
    return {logical:ts.coordinateToLogical(p.x),price:ps.coordinateToPrice(p.y)};
  }
  down(e){
    if(this.mode==="select")return;
    const p=this.point(e), m=this.model(p);
    if(m.logical==null||m.price==null)return;
    this.drag={mode:this.mode,start:m,current:m};
    this.host.setPointerCapture?.(e.pointerId); this.render();
  }
  move(e){
    if(!this.drag)return;
    const p=this.point(e),m=this.model(p);
    if(m.logical!=null&&m.price!=null){this.drag.current=m;this.render();}
  }
  up(){
    if(!this.drag)return;
    const d=this.drag;
    this.items.push({type:d.mode,p1:d.start,p2:d.current});
    this.drag=null; this.mode="select"; this.render();
  }
  clear(){this.items=[];this.render()}
  coords(p){
    const x=this.chart.timeScale().logicalToCoordinate(p.logical);
    const y=this.chart.priceScale("right").priceToCoordinate(p.price);
    return {x,y};
  }
  render(){
    this.svg.replaceChildren();
    const all=this.drag?[...this.items,{type:this.drag.mode,p1:this.drag.start,p2:this.drag.current}]:this.items;
    for(const d of all){
      const a=this.coords(d.p1),b=this.coords(d.p2); if(a.x==null||a.y==null||b.x==null||b.y==null)continue;
      let el;
      if(d.type==="trend"){
        el=document.createElementNS(this.svg.namespaceURI,"line");
        el.setAttribute("x1",a.x);el.setAttribute("y1",a.y);el.setAttribute("x2",b.x);el.setAttribute("y2",b.y);
      }else if(d.type==="horizontal"){
        el=document.createElementNS(this.svg.namespaceURI,"line");
        el.setAttribute("x1",0);el.setAttribute("x2",this.host.clientWidth);el.setAttribute("y1",a.y);el.setAttribute("y2",a.y);
      }else if(d.type==="vertical"){
        el=document.createElementNS(this.svg.namespaceURI,"line");
        el.setAttribute("x1",a.x);el.setAttribute("x2",a.x);el.setAttribute("y1",0);el.setAttribute("y2",this.host.clientHeight);
      }else if(d.type==="box"){
        el=document.createElementNS(this.svg.namespaceURI,"rect");
        el.setAttribute("x",Math.min(a.x,b.x));el.setAttribute("y",Math.min(a.y,b.y));el.setAttribute("width",Math.abs(a.x-b.x));el.setAttribute("height",Math.abs(a.y-b.y));
        el.setAttribute("fill","rgba(120,160,220,.14)");
      }
      if(el){el.setAttribute("stroke","#8fb3d9");el.setAttribute("stroke-width","2");el.setAttribute("vector-effect","non-scaling-stroke");el.setAttribute("fill",el.tagName==="rect"?"rgba(120,160,220,.14)":"none");this.svg.appendChild(el)}
    }
  }
}
