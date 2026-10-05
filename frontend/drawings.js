const MODES=new Set(["trend","horizontal","vertical","box"]);
export class DrawingManager {
  constructor(chart,host){
    this.chart=chart;this.host=host;this.items=[];this.mode="select";this.drag=null;
    this.svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    Object.assign(this.svg.style,{position:"absolute",inset:"0",width:"100%",height:"100%",pointerEvents:"none"});
    host.style.position="relative";host.appendChild(this.svg);
    host.addEventListener("pointerdown",e=>this.down(e));host.addEventListener("pointermove",e=>this.move(e));
    host.addEventListener("pointerup",e=>this.up(e));host.addEventListener("pointercancel",e=>this.up(e));
    window.addEventListener("resize",()=>this.render());this.render();
  }
  setMode(mode){this.mode=MODES.has(mode)?mode:"select"}
  point(e){const r=this.host.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top}}
  model(p){return{logical:this.chart.timeScale().coordinateToLogical(p.x),price:this.chart.priceScale("right").coordinateToPrice(p.y)}}
  down(e){if(!MODES.has(this.mode)||this.drag)return;const m=this.model(this.point(e));if(m.logical==null||m.price==null)return;this.drag={type:this.mode,p1:m,p2:m};this.host.setPointerCapture?.(e.pointerId);this.render()}
  move(e){if(!this.drag)return;const m=this.model(this.point(e));if(m.logical!=null&&m.price!=null){this.drag.p2=m;this.render()}}
  up(e){if(!this.drag)return;this.items.push({...this.drag});this.drag=null;this.mode="select";this.host.releasePointerCapture?.(e.pointerId);this.render()}
  clear(){this.items=[];this.render()}
  serialize(){return this.items.map(({type,p1,p2})=>({type,p1,p2}))}
  restore(items){this.items=Array.isArray(items)?items.filter(d=>MODES.has(d?.type)&&d?.p1&&d?.p2):[];this.render()}
  coords(p){return{x:this.chart.timeScale().logicalToCoordinate(p.logical),y:this.chart.priceScale("right").priceToCoordinate(p.price)}}
  render(){
    this.svg.replaceChildren();const all=this.drag?[...this.items,this.drag]:this.items;
    for(const d of all){const a=this.coords(d.p1),b=this.coords(d.p2);if([a.x,a.y,b.x,b.y].some(v=>v==null||!Number.isFinite(v)))continue;
      let el;if(d.type==="trend"){el=document.createElementNS(this.svg.namespaceURI,"line");el.setAttribute("x1",a.x);el.setAttribute("y1",a.y);el.setAttribute("x2",b.x);el.setAttribute("y2",b.y)}
      else if(d.type==="horizontal"){el=document.createElementNS(this.svg.namespaceURI,"line");el.setAttribute("x1",0);el.setAttribute("x2",this.host.clientWidth);el.setAttribute("y1",a.y);el.setAttribute("y2",a.y)}
      else if(d.type==="vertical"){el=document.createElementNS(this.svg.namespaceURI,"line");el.setAttribute("x1",a.x);el.setAttribute("x2",a.x);el.setAttribute("y1",0);el.setAttribute("y2",this.host.clientHeight)}
      else {el=document.createElementNS(this.svg.namespaceURI,"rect");el.setAttribute("x",Math.min(a.x,b.x));el.setAttribute("y",Math.min(a.y,b.y));el.setAttribute("width",Math.abs(a.x-b.x));el.setAttribute("height",Math.abs(a.y-b.y));el.setAttribute("fill","rgba(120,160,220,.14)")}
      el.setAttribute("stroke","#8fb3d9");el.setAttribute("stroke-width","2");el.setAttribute("vector-effect","non-scaling-stroke");this.svg.appendChild(el)
    }
  }
}