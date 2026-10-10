'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button, Input, Card, toast } from '@/components/ui';
import Link from 'next/link';

import { Suspense } from 'react';

function ResidentLoginForm() {
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [step, setStep] = useState<'phone' | 'otp'>('phone');
  const [loading, setLoading] = useState(false);
  const [consent, setConsent] = useState(false);
  
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get('returnTo') || searchParams.get('next') || '/';
  
  const isDev = process.env.NEXT_PUBLIC_DEV === 'true';

  const requestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!consent) return toast('You must agree to the privacy policy to continue.');
    setLoading(true);
    try {
      await api('/auth/otp/request', {
        method: 'POST',
        body: JSON.stringify({ phone })
      });
      setStep('otp');
      toast('OTP sent to your mobile.');
    } catch (err: any) {
      toast(err.message || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api<any>('/auth/otp/verify', {
        method: 'POST',
        body: JSON.stringify({ phone, otp })
      });
      if (res?.access_token) {
        localStorage.setItem('access_token', res.access_token);
        if (res.user) localStorage.setItem('resident_user', JSON.stringify(res.user));
        window.dispatchEvent(new Event('resident-auth-changed'));
        toast('Logged in successfully!');
        router.push(returnTo);
      }
    } catch (err: any) {
      toast(err.message || 'Invalid OTP');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md p-8 bg-white shadow-xl rounded-2xl">
      <h1 className="text-2xl font-bold mb-2 text-center text-gray-900">Resident Login</h1>
      <p className="text-center text-gray-600 mb-6 text-sm">Follow projects and submit feedback securely.</p>
      
      {step === 'phone' ? (
        <form onSubmit={requestOtp} className="flex flex-col gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mobile Number</label>
            <Input 
              type="tel" 
              value={phone} 
              onChange={e => setPhone(e.target.value)} 
              placeholder="e.g., 9876543210" 
              required 
              className="w-full"
            />
          </div>
          <label className="flex items-start gap-3 text-sm text-gray-600 bg-blue-50 p-3 rounded-lg border border-blue-100">
            <input 
              type="checkbox" 
              checked={consent} 
              onChange={e => setConsent(e.target.checked)} 
              className="mt-1"
              required
            />
            <span>
              I consent to the collection of my mobile number for the sole purpose of receiving project updates and tracking my feedback, in accordance with the DPDP Act. 
              Read our <Link href="/privacy" className="text-blue-600 underline">Privacy Policy</Link>.
            </span>
          </label>
          <Button type="submit" disabled={loading} className="w-full py-3 text-lg">
            {loading ? 'Sending...' : 'Send OTP'}
          </Button>
        </form>
      ) : (
        <form onSubmit={verifyOtp} className="flex flex-col gap-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Enter OTP</label>
            <Input 
              type="text" 
              value={otp} 
              onChange={e => setOtp(e.target.value)} 
              placeholder="6-digit code" 
              required 
              maxLength={6}
              className="w-full text-center tracking-widest text-lg font-mono"
            />
            {isDev && <div className="text-xs text-orange-600 mt-2 text-center">Dev Hint: Use 123456</div>}
          </div>
          <Button type="submit" disabled={loading} className="w-full py-3 text-lg">
            {loading ? 'Verifying...' : 'Verify & Login'}
          </Button>
          <button type="button" onClick={() => setStep('phone')} className="text-sm text-gray-500 underline text-center hover:text-gray-800">
            Change Mobile Number
          </button>
        </form>
      )}
    </Card>
  );
}

export default function ResidentLogin() {
  return (
    <div className="flex h-screen items-center justify-center bg-gray-50 p-4">
      <Suspense fallback={<Card className="w-full max-w-md p-8 bg-white shadow-xl rounded-2xl text-center">Loading...</Card>}>
        <ResidentLoginForm />
      </Suspense>
    </div>
  );
}
