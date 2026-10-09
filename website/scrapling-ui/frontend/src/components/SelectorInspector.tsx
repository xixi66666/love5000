import React, { useState } from 'react';
import { Copy, Check, Eye } from 'lucide-react';
import type { DOMNode } from '../types';

interface SelectorInspectorProps {
  selectedNode: DOMNode | null;
}

function scoreSelectorQuality(sel: string): { score: number; label: string; issues: string[] } {
  const issues: string[] = [];
  let score = 100;

  if (!sel) return { score: 0, label: '无', issues: ['未提供选择器'] };

  if (sel.startsWith('*')) { score -= 20; issues.push('通配选择器 (*) 不稳定'); }
  if (sel.includes(':nth-of-type') || sel.includes(':nth-child')) {
    score -= 15; issues.push('使用了 :nth-*，DOM 变化时容易失效');
  }
  const tagOnly = /^[a-z]+$/i.test(sel);
  if (tagOnly) { score -= 25; issues.push('纯标签选择器会匹配过多元素'); }
  if (sel.includes('#') && !sel.match(/#[a-zA-Z][a-zA-Z0-9_-]*/)) {
    score -= 10; issues.push('ID 包含异常字符');
  }
  const parts = sel.split(/>/);
  if (parts.length > 3) { score -= 10; issues.push('嵌套层级过深（>3 层），非常不稳定'); }
  else if (parts.length > 2) { score -= 5; issues.push('嵌套选择器（>2 层），可能不稳定'); }
  if (sel.includes('[class') || sel.includes('[id')) { score -= 10; issues.push('依赖生成的 class/id 属性'); }

  let label = '优秀';
  if (score < 30) label = '极弱';
  else if (score < 50) label = '较弱';
  else if (score < 70) label = '一般';
  else if (score < 85) label = '良好';

  return { score: Math.max(0, score), label, issues };
}

export const SelectorInspector: React.FC<SelectorInspectorProps> = ({ selectedNode }) => {
  const [copiedSelector, setCopiedSelector] = useState(false);
  const [copiedXPath, setCopiedXPath] = useState(false);

  const quality = selectedNode ? scoreSelectorQuality(selectedNode.selector) : null;

  const copySelector = () => {
    if (!selectedNode) return;
    navigator.clipboard.writeText(selectedNode.selector);
    setCopiedSelector(true);
    setTimeout(() => setCopiedSelector(false), 2000);
  };

  const copyXPath = () => {
    if (!selectedNode) return;
    navigator.clipboard.writeText(selectedNode.xpath);
    setCopiedXPath(true);
    setTimeout(() => setCopiedXPath(false), 2000);
  };

  if (!selectedNode) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', gap: '10px', textAlign: 'center', padding: '20px' }}>
        <Eye size={28} />
        <div style={{ fontSize: '13px' }}>点击视图截图中的任意元素，在此查看详情。</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Tag name and classes header */}
      <div style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{
            fontSize: '11px',
            fontWeight: 700,
            textTransform: 'uppercase',
            backgroundColor: 'rgba(99, 102, 241, 0.1)',
            color: 'var(--accent-primary)',
            padding: '2px 6px',
            borderRadius: '4px'
          }}>
            HTML 标签
          </span>
          <span style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#ec4899' }}>
            &lt;{selectedNode.tag}&gt;
          </span>
        </div>
        
        {selectedNode.classes ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
            {selectedNode.classes.split(' ').map((cls, idx) => (
              <span key={idx} style={{
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                backgroundColor: 'rgba(255,255,255,0.04)',
                border: '1px solid var(--border-light)',
                color: 'var(--text-secondary)',
                padding: '1px 6px',
                borderRadius: '4px'
              }}>
                .{cls}
              </span>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>没有 CSS 类。</div>
        )}
      </div>

      {/* Target Selector */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>CSS 选择器</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{
            flex: 1,
            background: 'var(--bg-main)',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 12px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--accent-secondary)',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}>
            {selectedNode.selector}
          </div>
          <button
            className="btn btn-secondary"
            onClick={copySelector}
            style={{ width: '36px', height: '34px', padding: 0 }}
            title="复制选择器"
          >
            {copiedSelector ? <Check size={14} color="var(--accent-secondary)" /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      {/* XPath */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>XPath 选择器</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{
            flex: 1,
            background: 'var(--bg-main)',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 12px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--accent-primary)',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}>
            {selectedNode.xpath}
          </div>
          <button
            className="btn btn-secondary"
            onClick={copyXPath}
            style={{ width: '36px', height: '34px', padding: 0 }}
            title="复制 XPath"
          >
            {copiedXPath ? <Check size={14} color="var(--accent-secondary)" /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      {/* Selector Quality Score */}
      {quality && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          background: 'rgba(255,255,255,0.01)',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--radius-md)',
          padding: '10px 12px'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '13px',
            fontFamily: 'var(--font-mono)',
            flexShrink: 0,
            background: quality.score >= 85 ? 'rgba(16, 185, 129, 0.15)' : quality.score >= 70 ? 'rgba(234, 179, 8, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            color: quality.score >= 85 ? '#10b981' : quality.score >= 70 ? '#eab308' : '#ef4444',
            border: `2px solid ${quality.score >= 85 ? '#10b981' : quality.score >= 70 ? '#eab308' : '#ef4444'}`
          }}>
            {quality.score}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
              选择器质量：{quality.label}
            </div>
            {quality.issues.length > 0 && (
              <ul style={{ margin: '4px 0 0', paddingLeft: '16px', fontSize: '10.5px', color: 'var(--text-muted)' }}>
                {quality.issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Box details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
        <div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block' }}>位置</span>
          <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>X: {selectedNode.rect.x}px, Y: {selectedNode.rect.y}px</span>
        </div>
        <div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block' }}>尺寸</span>
          <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{selectedNode.rect.width} × {selectedNode.rect.height} px</span>
        </div>
      </div>

      {/* Text preview */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>文本内容</span>
        <div style={{
          background: 'var(--bg-main)',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--radius-md)',
          padding: '10px 12px',
          fontSize: '13px',
          color: 'var(--text-primary)',
          maxHeight: '120px',
          overflowY: 'auto',
          wordBreak: 'break-all',
          whiteSpace: 'pre-wrap'
        }}>
          {selectedNode.text ? selectedNode.text : <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>没有直接文本内容。</span>}
        </div>
      </div>
    </div>
  );
};
