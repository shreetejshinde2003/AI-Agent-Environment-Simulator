import {useState} from "react";
import Modal from "../common/Modal";
import {presentOutput} from "../../utils/outputPresentation";
import "./OutputViewer.css";

// React escapes all content. Raw HTML, images and executable links are never inserted.
function Inline({text}) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g).map((part,i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2,-2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i}>{part.slice(1,-1)}</code>;
    if (part.startsWith("*") && part.endsWith("*")) return <em key={i}>{part.slice(1,-1)}</em>;
    const link=part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if(link)return <a key={i} href={link[2]} rel="noreferrer" target="_blank">{link[1]}</a>;
    return part;
  });
}
export function MarkdownOutput({text}) {
  const lines=text.split("\n"), blocks=[];
  for(let i=0;i<lines.length;i++) {
    const line=lines[i];
    if(line.startsWith("```")) {const code=[];while(++i<lines.length&&!lines[i].startsWith("```"))code.push(lines[i]);blocks.push(<pre key={i}><code>{code.join("\n")}</code></pre>);continue;}
    const heading=line.match(/^(#{1,6})\s+(.+)$/);
    if(heading){const Tag=`h${Math.min(heading[1].length+1,6)}`;blocks.push(<Tag key={i}><Inline text={heading[2]}/></Tag>);continue;}
    if(/^\|/.test(line)&&/^\|?\s*:?-+/.test(lines[i+1]??"")) {
      const cells=value=>value.replace(/^\||\|$/g,"").split("|").map(v=>v.trim());
      const headers=cells(line),rows=[];i+=2;while(i<lines.length&&/^\|/.test(lines[i]))rows.push(cells(lines[i++]));i--;
      blocks.push(<div className="table-scroll" key={i}><table><thead><tr>{headers.map((v,n)=><th key={n}><Inline text={v}/></th>)}</tr></thead><tbody>{rows.map((row,n)=><tr key={n}>{row.map((v,c)=><td key={c}><Inline text={v}/></td>)}</tr>)}</tbody></table></div>);continue;
    }
    if(/^\s*(?:[-*+] |\d+[.)] )/.test(line)) {const ordered=/^\s*\d/.test(line),items=[];const pattern=ordered?/^\s*\d+[.)] (.*)/:/^\s*[-*+] (.*)/;
      while(i<lines.length&&pattern.test(lines[i])){let content=lines[i++].replace(pattern,"$1");while(i<lines.length&&/^\s{2,}\S/.test(lines[i])&&!/^\s*(?:[-*+] |\d+[.)] )/.test(lines[i]))content+="\n"+lines[i++].trim();items.push(content);}i--;
      const Tag=ordered?"ol":"ul";blocks.push(<Tag key={i}>{items.map((v,n)=><li key={n}><Inline text={v}/></li>)}</Tag>);continue;}
    if(line.startsWith("> ")){blocks.push(<blockquote key={i}><Inline text={line.slice(2)}/></blockquote>);continue;}
    if(line.trim())blocks.push(<p key={i}><Inline text={line}/></p>);
  }
  return <div className="output-markdown">{blocks}</div>;
}
export default function OutputViewer({text, directive = "", contract, label = "Final answer", intermediate = false}) {
  const [raw,setRaw]=useState(false),[expanded,setExpanded]=useState(!intermediate),[focused,setFocused]=useState(false),[copied,setCopied]=useState("");
  if(text==null)return <p className="empty-note">No {intermediate ? "stage output" : "final result"} recorded.</p>;
  const presented=presentOutput(text,directive,contract);
  function body(){return raw?<pre className="output-text">{text}</pre>:presented.type==="markdown"?<MarkdownOutput text={presented.text}/>:<pre className="output-text">{presented.text}</pre>;}
  async function copy(){try{await navigator.clipboard.writeText(raw?text:presented.text);setCopied("Copied");}catch{setCopied("Copy unavailable; select the output text.");}}
  const controls=<div className="output-controls"><button type="button" aria-pressed={!raw} onClick={()=>setRaw(false)}>Rendered</button><button type="button" aria-pressed={raw} onClick={()=>setRaw(true)}>Raw</button><button type="button" onClick={copy}>Copy output</button><span role="status">{copied}</span></div>;
  return <section className={`output-viewer ${intermediate?"intermediate-output":"final-output"}`} aria-label={label}>
    <div className="output-heading"><h3>{label}</h3><button type="button" onClick={()=>setFocused(true)}>Focus reading</button></div>
    {!!presented.issues.length&&<p className="output-problem" role="status">Output contract problem: {presented.issues.join(", ").replaceAll("_"," ")}. Presentation may be normalized; Raw preserves the recorded response.</p>}
    {intermediate&&!expanded?<><p className="output-preview">{presented.text.slice(0,280)}{presented.text.length>280?"…":""}</p><button type="button" onClick={()=>setExpanded(true)}>Expand full output · {text.length.toLocaleString()} characters</button></>:<>{controls}<div className="output-body" tabIndex={0} role="region" aria-label={`${label} content`}>{body()}</div>{intermediate&&<button type="button" onClick={()=>setExpanded(false)}>Collapse output</button>}</>}
    {focused&&<Modal title={label} className="output-reading-modal" onClose={()=>setFocused(false)}>{controls}<div className="output-body">{body()}</div></Modal>}
  </section>;
}
