import { useState } from 'react';
import type { BlockDef, FieldDef, FieldListData } from '../api';

interface Props {
  fieldList: FieldListData;
  changedKeys: Set<string>; // "BLOCK:FIELD" keys touched by the last AI correction
  onChange: (next: FieldListData) => void;
}

export default function FieldListPanel({ fieldList, changedKeys, onChange }: Props) {
  return (
    <div className="flex flex-col gap-3 p-4">
      {fieldList.blocks.map(block => (
        <BlockCard
          key={block.name}
          block={block}
          changedKeys={changedKeys}
          onChange={updated => {
            onChange({
              ...fieldList,
              blocks: fieldList.blocks.map(b => (b.name === block.name ? updated : b)),
            });
          }}
        />
      ))}

      <ParametersCard fieldList={fieldList} onChange={onChange} />
    </div>
  );
}

// ---------------------------------------------------------------------------

function BlockCard({
  block,
  changedKeys,
  onChange,
}: {
  block: BlockDef;
  changedKeys: Set<string>;
  onChange: (b: BlockDef) => void;
}) {
  const [open, setOpen] = useState(true);
  const [adding, setAdding] = useState(false);

  function updateField(index: number, next: FieldDef) {
    onChange({ ...block, fields: block.fields.map((f, i) => (i === index ? next : f)) });
  }

  function deleteField(index: number) {
    onChange({ ...block, fields: block.fields.filter((_, i) => i !== index) });
  }

  function addField(f: FieldDef) {
    onChange({ ...block, fields: [...block.fields, f] });
    setAdding(false);
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800/80 transition-colors text-left"
      >
        <span className={`text-slate-500 text-xs transition-transform ${open ? 'rotate-90' : ''}`}>▶</span>
        <span className="font-semibold text-sm text-slate-100">{block.name}</span>
        {block.parent ? (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-orange-950/60 text-orange-300/90">
            detail of {block.parent}
          </span>
        ) : (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300">
            header
          </span>
        )}
        <span className="ml-auto text-xs text-slate-500">{block.fields.length} fields</span>
      </button>

      {open && (
        <div>
          {block.fields.map((f, i) => (
            <FieldRow
              key={`${f.name}-${i}`}
              field={f}
              highlight={changedKeys.has(`${block.name}:${f.name}`)}
              onChange={next => updateField(i, next)}
              onDelete={() => deleteField(i)}
            />
          ))}

          {adding ? (
            <NewFieldRow onSave={addField} onCancel={() => setAdding(false)} />
          ) : (
            <button
              onClick={() => setAdding(true)}
              className="w-full px-4 py-2 text-left text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 transition-colors border-t border-slate-800"
            >
              + Add field
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function FieldRow({
  field,
  highlight,
  onChange,
  onDelete,
}: {
  field: FieldDef;
  highlight: boolean;
  onChange: (f: FieldDef) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(field.name);
  const [dataType, setDataType] = useState(field.data_type);

  function save() {
    const trimmedName = name.trim().toUpperCase();
    const trimmedType = dataType.trim().toUpperCase();
    if (!trimmedName || !trimmedType) {
      setName(field.name);
      setDataType(field.data_type);
    } else {
      onChange({ ...field, name: trimmedName, data_type: trimmedType });
    }
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 border-t border-slate-800 bg-slate-800/40">
        <input
          autoFocus
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && save()}
          className="flex-1 min-w-0 rounded bg-slate-950 border border-indigo-500 px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none"
        />
        <input
          value={dataType}
          onChange={e => setDataType(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && save()}
          className="w-36 rounded bg-slate-950 border border-indigo-500 px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none"
        />
        <button onClick={save} className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0">Save</button>
        <button
          onClick={() => { setName(field.name); setDataType(field.data_type); setEditing(false); }}
          className="text-xs text-slate-500 hover:text-slate-300 shrink-0"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div
      className={`group flex items-center gap-2 px-4 py-2 border-t border-slate-800 transition-colors
        ${highlight ? 'bg-indigo-950/40' : 'hover:bg-slate-800/30'}`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-200 truncate">{field.name}</span>
          {field.hidden && (
            <span
              className="text-[10px] px-1.5 py-0.5 rounded-full bg-sky-950/80 text-sky-300 shrink-0"
              title={field.note ?? undefined}
            >
              hidden{highlight ? ' · added by AI' : ''}
            </span>
          )}
        </div>
        {field.source && (
          <p className="text-[10px] text-slate-600 font-mono truncate mt-0.5">{field.source}</p>
        )}
      </div>
      <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-950/70 text-emerald-300 font-mono shrink-0">
        {field.data_type}
      </span>
      <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button onClick={() => setEditing(true)} className="text-xs text-slate-500 hover:text-slate-200" title="Edit">✎</button>
        <button onClick={onDelete} className="text-xs text-slate-500 hover:text-red-400" title="Delete">✕</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function NewFieldRow({
  onSave,
  onCancel,
}: {
  onSave: (f: FieldDef) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [dataType, setDataType] = useState('VARCHAR2(100)');

  function save() {
    const n = name.trim().toUpperCase();
    const t = dataType.trim().toUpperCase();
    if (!n || !t) return;
    onSave({ name: n, data_type: t, hidden: false, source: null, note: null });
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-t border-slate-800 bg-slate-800/40">
      <input
        autoFocus
        placeholder="FIELD_NAME"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && save()}
        className="flex-1 min-w-0 rounded bg-slate-950 border border-indigo-500 px-2 py-1 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none"
      />
      <input
        value={dataType}
        onChange={e => setDataType(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && save()}
        className="w-36 rounded bg-slate-950 border border-indigo-500 px-2 py-1 text-xs font-mono text-slate-100 focus:outline-none"
      />
      <button onClick={save} className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0">Add</button>
      <button onClick={onCancel} className="text-xs text-slate-500 hover:text-slate-300 shrink-0">Cancel</button>
    </div>
  );
}

// ---------------------------------------------------------------------------

function ParametersCard({
  fieldList,
  onChange,
}: {
  fieldList: FieldListData;
  onChange: (next: FieldListData) => void;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800/80 transition-colors text-left"
      >
        <span className={`text-slate-500 text-xs transition-transform ${open ? 'rotate-90' : ''}`}>▶</span>
        <span className="font-semibold text-sm text-slate-100">Report parameters</span>
        <span className="ml-auto text-xs text-slate-500">{fieldList.parameters.length}</span>
      </button>
      {open && fieldList.parameters.map((p, i) => (
        <div key={`${p.name}-${i}`} className="group flex items-center gap-2 px-4 py-2 border-t border-slate-800 hover:bg-slate-800/30">
          <span className="flex-1 text-xs font-mono text-slate-200">{p.name}</span>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-950/70 text-emerald-300 font-mono">
            {p.data_type}
          </span>
          <button
            onClick={() => onChange({
              ...fieldList,
              parameters: fieldList.parameters.filter((_, j) => j !== i),
            })}
            className="text-xs text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
            title="Delete"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
