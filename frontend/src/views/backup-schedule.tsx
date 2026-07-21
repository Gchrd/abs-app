"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Calendar, ListChecks } from "lucide-react";
import { SchedulesPage } from "./schedules";
import { JobsPage } from "./jobs";

export function BackupSchedulePage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-foreground">Backup Schedule</h2>
        <p className="text-muted-foreground">Configure automated schedules and monitor backup job runs</p>
      </div>

      <Tabs defaultValue="schedules">
        <TabsList>
          <TabsTrigger value="schedules" className="gap-1.5">
            <Calendar className="w-4 h-4" /> Schedules
          </TabsTrigger>
          <TabsTrigger value="jobs" className="gap-1.5">
            <ListChecks className="w-4 h-4" /> Job History
          </TabsTrigger>
        </TabsList>
        <TabsContent value="schedules">
          <SchedulesPage />
        </TabsContent>
        <TabsContent value="jobs">
          <JobsPage />
        </TabsContent>
      </Tabs>
    </div>
  );
}
