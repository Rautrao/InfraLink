'use client';
import { Card } from '@/components/ui';

export default function PrivacyPolicy() {
  return (
    <div className="max-w-3xl mx-auto py-12 px-4 flex flex-col gap-8">
      <h1 className="text-3xl font-bold">Privacy Policy & Data Protection</h1>
      <Card className="p-8 prose">
        <p>
          At Demo City Public Works, we are committed to protecting your privacy in compliance with the Digital Personal Data Protection (DPDP) Act.
        </p>
        
        <h3 className="text-xl font-bold mt-6 mb-2">1. Data Collection & Purpose</h3>
        <p>
          We collect your mobile number solely for authentication (OTP) and to send you requested updates about public works or responses to your feedback.
          Your location data is only collected if you explicitly provide it when submitting a feedback ticket, to help engineers locate issues.
        </p>

        <h3 className="text-xl font-bold mt-6 mb-2">2. Data Sharing</h3>
        <p>
          Your contact information is strictly confidential. It is accessible only to authorized municipal engineers assigned to your feedback tickets. 
          When your feedback is published on the public portal, your name and phone number are completely anonymized or hidden.
        </p>

        <h3 className="text-xl font-bold mt-6 mb-2">3. Data Retention & Deletion Request</h3>
        <p>
          We retain your account data only as long as necessary to provide you with project updates. 
          You have the right to request immediate deletion of your account and all associated personal data. 
          To do so, please email <strong>privacy@demo.city</strong> or visit your Ward Office.
        </p>
      </Card>
    </div>
  );
}
