import React from 'react';
import {resolveMarkdownAsset} from './preview.js';

const inlineToken=/(!?\[[^\]]*\]\([^)]+\)|`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|~~[^~\n]+~~|\*[^*\n]+\*|_[^_\n]+_)/g;

function safeExternalUrl(value,image=false){
  const target=value.trim();
  if(/^https?:\/\//i.test(target)||/^mailto:/i.test(target)||target.startsWith('#'))return target;
  if(image&&/^data:image\/(?:avif|gif|jpeg|png|webp);base64,/i.test(target))return target;
  return '';
}

function inlineMarkdown(text,keyPrefix,assetUrlFor){
  const nodes=[],matches=[...String(text).matchAll(inlineToken)];let cursor=0;
  matches.forEach((match,index)=>{
    if(match.index>cursor)nodes.push(text.slice(cursor,match.index));
    const token=match[0],key=`${keyPrefix}-${index}`;
    if(token.startsWith('![')){
      const parsed=token.match(/^!\[([^\]]*)\]\(([^)]+)\)$/),src=parsed&&(safeExternalUrl(parsed[2],true)||assetUrlFor?.(parsed[2]));
      nodes.push(src?<img className="markdown-inline-image" src={src} alt={parsed[1]} loading="lazy" key={key}/>:<span key={key}>{parsed?.[1]||token}</span>);
    }else if(token.startsWith('[')){
      const parsed=token.match(/^\[([^\]]*)\]\(([^)]+)\)$/),href=parsed&&safeExternalUrl(parsed[2]);
      nodes.push(href?<a href={href} target={/^https?:/i.test(href)?'_blank':undefined} rel="noreferrer" key={key}>{parsed[1]}</a>:<span key={key}>{parsed?.[1]||token}</span>);
    }else if(token.startsWith('`')) nodes.push(<code key={key}>{token.slice(1,-1)}</code>);
    else if(token.startsWith('**')||token.startsWith('__')) nodes.push(<strong key={key}>{inlineMarkdown(token.slice(2,-2),key,assetUrlFor)}</strong>);
    else if(token.startsWith('~~')) nodes.push(<del key={key}>{inlineMarkdown(token.slice(2,-2),key,assetUrlFor)}</del>);
    else nodes.push(<em key={key}>{inlineMarkdown(token.slice(1,-1),key,assetUrlFor)}</em>);
    cursor=match.index+token.length;
  });
  if(cursor<text.length)nodes.push(text.slice(cursor));
  return nodes.length?nodes:text;
}

const splitCells=line=>line.trim().replace(/^\||\|$/g,'').split('|').map(cell=>cell.trim());
const isTableDivider=line=>/^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
const isBlockStart=(lines,index)=>/^\s*(?:```|#{1,6}\s|>|[-*_](?:\s*[-*_]){2,}\s*$|[-+*]\s+|\d+[.)]\s+)/.test(lines[index])||(lines[index].includes('|')&&isTableDivider(lines[index+1]||''));

function renderBlocks(content,assetUrlFor,keyPrefix='md'){
  const lines=String(content??'').replace(/\r\n?/g,'\n').split('\n'),blocks=[];let index=0;
  while(index<lines.length){
    const line=lines[index];
    if(!line.trim()){index++;continue}
    const fence=line.match(/^\s*```\s*([^\s`]*)/);
    if(fence){
      const code=[];index++;
      while(index<lines.length&&!/^\s*```/.test(lines[index]))code.push(lines[index++]);
      if(index<lines.length)index++;
      blocks.push(<pre key={`${keyPrefix}-${index}`} dir="ltr"><code className={fence[1]?`language-${fence[1]}`:undefined}>{code.join('\n')}</code></pre>);continue;
    }
    const heading=line.match(/^\s*(#{1,6})\s+(.+)$/);
    if(heading){const level=heading[1].length;blocks.push(React.createElement(`h${level}`,{key:`${keyPrefix}-${index}`},inlineMarkdown(heading[2],`${keyPrefix}-${index}`,assetUrlFor)));index++;continue}
    if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)){blocks.push(<hr key={`${keyPrefix}-${index}`}/>);index++;continue}
    if(line.includes('|')&&isTableDivider(lines[index+1]||'')){
      const headers=splitCells(line),rows=[];index+=2;
      while(index<lines.length&&lines[index].includes('|')&&lines[index].trim())rows.push(splitCells(lines[index++]));
      blocks.push(<div className="markdown-table-wrap" key={`${keyPrefix}-table-${index}`}><table><thead><tr>{headers.map((cell,i)=><th key={i}>{inlineMarkdown(cell,`${keyPrefix}-th-${i}`,assetUrlFor)}</th>)}</tr></thead><tbody>{rows.map((row,r)=><tr key={r}>{headers.map((_,c)=><td key={c}>{inlineMarkdown(row[c]||'',`${keyPrefix}-td-${r}-${c}`,assetUrlFor)}</td>)}</tr>)}</tbody></table></div>);continue;
    }
    if(/^\s*>/.test(line)){
      const quote=[];
      while(index<lines.length&&/^\s*>/.test(lines[index]))quote.push(lines[index++].replace(/^\s*>\s?/,''));
      blocks.push(<blockquote key={`${keyPrefix}-quote-${index}`}>{renderBlocks(quote.join('\n'),assetUrlFor,`${keyPrefix}-quote-${index}`)}</blockquote>);continue;
    }
    const list=line.match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);
    if(list){
      const ordered=/^\d/.test(list[1]),items=[];
      while(index<lines.length){
        const item=lines[index].match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);
        if(!item||/^\d/.test(item[1])!==ordered)break;
        const task=item[2].match(/^\[([ xX])\]\s+(.*)$/);
        items.push(task?<><input type="checkbox" checked={task[1].toLowerCase()==='x'} readOnly/>{inlineMarkdown(task[2],`${keyPrefix}-li-${index}`,assetUrlFor)}</>:inlineMarkdown(item[2],`${keyPrefix}-li-${index}`,assetUrlFor));index++;
      }
      blocks.push(React.createElement(ordered?'ol':'ul',{key:`${keyPrefix}-list-${index}`},items.map((item,i)=><li key={i}>{item}</li>)));continue;
    }
    const paragraph=[line.trim()];index++;
    while(index<lines.length&&lines[index].trim()&&!isBlockStart(lines,index))paragraph.push(lines[index++].trim());
    blocks.push(<p key={`${keyPrefix}-p-${index}`}>{inlineMarkdown(paragraph.join(' '),`${keyPrefix}-p-${index}`,assetUrlFor)}</p>);
  }
  return blocks;
}

export default function MarkdownPreview({content,path,rawUrlFor}){
  const assetUrlFor=target=>{
    const external=safeExternalUrl(target,true);
    if(external)return external;
    const resolved=resolveMarkdownAsset(path,target);
    return resolved?rawUrlFor(resolved):'';
  };
  return <article className="markdown-preview" dir="auto">{renderBlocks(content,assetUrlFor)}</article>;
}
