'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button, Card, toast, Badge } from '@/components/ui';

export default function ImportWorks() {
  const [file, setFile] = useState<File | null>(null);
  const [dryRunResult, setDryRunResult] = useState<{ valid: any[], invalid: any[] } | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setDryRunResult(null);
    }
  };

  const uploadFile = async (dryRun: boolean) => {
    if (!file) return toast('Please select a file first.');
    setIsProcessing(true);
    const formData = new FormData();
    const fieldName = file.name.endsWith('.csv') ? 'csv_file' : 'geojson_file';
    formData.append(fieldName, file);

    try {
      // the api wrapper JSON-ifies by default, but we need raw fetch for FormData
      const token = localStorage.getItem('access_token');
      const res = await fetch(`/api/v1/works/import?dry_run=${dryRun}`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error?.message || 'Import failed');

      if (dryRun) {
        setDryRunResult(data);
        toast(`Dry run complete: ${data.valid?.length || 0} valid, ${data.invalid?.length || 0} invalid.`);
      } else {
        toast(`Successfully imported ${data.valid?.length || 0} works!`);
        setFile(null);
        setDryRunResult(null);
      }
    } catch (err: any) {
      toast(err.message || 'Import error');
    } finally {
      setIsProcessing(false);
    }
  };

  const downloadTemplate = async () => {
    const token = localStorage.getItem('access_token');
    const res = await fetch('/api/v1/works/import/template', {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {}
    });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'import_template.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Bulk Import Works</h1>
      
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Upload Data</h2>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-gray-600">Upload a CSV or GeoJSON file containing works. Download the template below to see the required format.</p>
          <div className="flex items-center gap-4">
            <input 
              type="file" 
              accept=".csv,.geojson,.json" 
              onChange={handleFileChange} 
              className="border p-2 rounded w-full max-w-md"
            />
            <Button tone="secondary" onClick={downloadTemplate}>Download Template</Button>
          </div>
          <div className="flex gap-4 mt-2">
            <Button onClick={() => uploadFile(true)} disabled={!file || isProcessing} tone="secondary">
              {isProcessing ? 'Processing...' : '1. Run Dry Run Validation'}
            </Button>
            <Button onClick={() => uploadFile(false)} disabled={!dryRunResult || dryRunResult.invalid?.length > 0 || isProcessing} tone="primary">
              2. Confirm & Import Valid Rows
            </Button>
          </div>
        </div>
      </Card>

      {dryRunResult && (
        <div className="flex flex-col gap-6">
          <Card className="p-6 border-green-200">
            <h3 className="font-bold text-green-800 mb-2">Valid Rows ({dryRunResult.valid?.length || 0})</h3>
            <div className="max-h-64 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead><tr><th>Title</th><th>Agency</th><th>Category</th></tr></thead>
                <tbody className="divide-y">
                  {dryRunResult.valid?.map((row, i) => (
                    <tr key={i}>
                      <td className="py-2">{row.title}</td>
                      <td>{row.agency_code}</td>
                      <td>{row.category}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {dryRunResult.invalid?.length > 0 && (
            <Card className="p-6 border-red-200 bg-red-50">
              <h3 className="font-bold text-red-800 mb-2">Invalid Rows ({dryRunResult.invalid.length})</h3>
              <p className="text-sm text-red-700 mb-4">You must fix these errors before importing.</p>
              <div className="max-h-64 overflow-y-auto bg-white rounded border">
                <table className="w-full text-left text-sm">
                  <thead className="bg-red-100"><tr><th>Title</th><th>Errors</th></tr></thead>
                  <tbody className="divide-y">
                    {dryRunResult.invalid.map((row, i) => (
                      <tr key={i}>
                        <td className="py-2 px-2">{row.row?.title || 'Unknown row'}</td>
                        <td className="py-2 px-2 text-red-600 font-medium">
                          {row.errors?.join(', ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
