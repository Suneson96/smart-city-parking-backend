## 1.0.0 (dd-mm-yy)

### New features

#### SCP-30 Add API endpoints
  * Added parking-lots endpoints
    * `GET: http://localhost:8000/parking-lots/`
    * `GET: http://localhost:8000/cadmin/parking-lots/`
    * `POST: http://localhost:8000/cadmin/parking-lots/`
    * `PUT: http://localhost:8000/cadmin/parking-lots/`
    * `DELETE: http://localhost:8000/cadmin/parking-lots/`

#### SCP-31 Integrate GeoBjangi fir geospatial support
  * Change parking lot location to a geospatial point

#### SCP-28 Add Django models
  * Added Django models for the database
  * Added serializers and admin registration for the models

#### SCP-18 Add sign in with google to backend
  * Added logic to login with google OAuth token.

#### SCP-16 Add Firebase authentication
  * Added basic Firebase authentication
    * Added endpoints
      * `POST: http://localhost:8000/signup/`
      * `POST: http://localhost:8000/login/`
      * `POST: http://localhost:8000/refresh-token/`

#### SCP-15 Create simple Django API
  * Add basic Django rest API
  * Add changelog

### Notable changes